# P-010 — Responder pipeline, predicate execution, output validation

| Field | Detail |
|---|---|
| PRD | P-010 |
| Stage | 4 |
| Status | **Ready for decomposition** |
| Size | L |
| Risk | medium |
| Depends on | [P-001](P-001-conformance-corpus.md), [P-002](P-002-message-envelope.md), [P-003](P-003-crypto-suites.md), [P-004](P-004-replay-idempotency.md), [P-005](P-005-registry-client.md), [P-006](P-006-request-validation.md), [P-007](P-007-policy-engine.md), [P-009](P-009-denial-normalization.md) — **P-008 removed 2026-08-19**, deferred with Q2D-C-09 |
| Blocks | P-011, P-016, [P-017](P-017-mcp-binding.md) — ~~P-013, P-015~~ deferred |

---

## 1. Purpose

Orchestrate [`core-model.md`](../../spec/core-model.md) §4's twenty-one steps into
a responder, evaluate registered predicates locally, and validate output against
the effective domain.

Nine modules exist by this point and none of them is a responder. This PRD is
where the ordering stops being a table and becomes a property.

**Claims served:** Q2D-C-03 (bounded output) and Q2D-C-04 (source confinement)
directly. Q2D-C-02, C-06, C-08, and C-09 are all *exercised* here — this is the
first module where they can fail in combination rather than in isolation.

## 2. Spec citations

| Source | What it constrains here |
|---|---|
| [`spec/core-model.md`](../../spec/core-model.md) §4 | The steps, their order, and the three invariants. **Nineteen numbered and three lettered** — 5a, 9a and 11a — so a pipeline that orchestrates 1–19 and stops has skipped three |
| [`spec/core-model.md`](../../spec/core-model.md) §4 step 17 | Output validation fails closed; the runtime must not serialize an exception carrying private input |
| [`spec/core-model.md`](../../spec/core-model.md) §5.1 | The `answer` response shape |
| [`spec/claims.md`](../../spec/claims.md) Q2D-C-03 | Bounded output, and what it does not claim |
| [`spec/claims.md`](../../spec/claims.md) Q2D-C-04 | Private input is not serialized into the response |
| [`spec/conformance-classes.md`](../../spec/conformance-classes.md) CC-2 | Must not read private input before step 16; must not reorder steps 1–16, **or 5a, 9a and 11a among them** |
| [`threat-model/trust-matrix.md`](../../threat-model/trust-matrix.md) §3 | The computation executor is the trusted component for C-03 and C-04 |
| [`registry/manifest.json`](../../registry/manifest.json) | The three predicates and their vectors |

## 3. Module boundary

**Inside:** step orchestration; the private-access gate; predicate dispatch and
execution; output validation; the evaluation error boundary; the step recorder.

**Explicitly outside:** every step's *logic*, which belongs to the module that
owns it — this PRD calls them in order and owns nothing they do. Receipt
construction (**P-011**), which consumes what this produces. Transport
(**P-013**). Escalation beyond returning the outcome (**P-015**).

## 4. Design

### 4.1 Ordering as a type, not a convention

Nineteen steps in a documented order is a comment. Two constructions make the two
orderings that matter unbreakable:

**Verification precedes parsing.** Already structural:
[P-003](P-003-crypto-suites.md)'s `verify` returns bytes, and
[P-002](P-002-message-envelope.md)'s `parse_core` takes bytes. There is no path
from a compact JWS to a parsed core object that skips verification.

**Private access requires a capability that only step 15 can mint.**

**Step 15 is the gate; what it checks is separate from what it mints.** It was
described as *the budget check*, and Q2D-C-09 is now **not attempted**
([`claims.md`](../../spec/claims.md)) so it checks nothing — but it still runs
and still mints the token, because the property is that **nothing below step 15
is reachable without having passed everything above it**. That never depended on
what step 15 checked. A pipeline that skipped step 15 because it had nothing to
do would make step 16 reachable directly, which is the one thing this type
exists to prevent.

```
PrivateAccessAuthorized     // constructible ONLY by step 15
read_private_input(auth: PrivateAccessAuthorized, ...) -> PrivateInput
```

The token has no public constructor. Steps 1–15, and 5a, 9a and 11a among them,
produce it or the request is
already rejected; step 16 consumes it. **"No private input before step 16"
becomes a fact about what compiles**, rather than a rule a reviewer checks.

This is the single most valuable structural guarantee in the implementation, and
it is why CC-2's *"must not read private input before step 16"* can be asserted
rather than audited.

The remaining seventeen orderings are ordinary sequential code plus §4.2.

### 4.2 The step recorder

Every rejection carries the step at which it occurred
([P-001](P-001-conformance-corpus.md) §4.6). The corpus asserts it.

The step is part of the **rejection value**, not test instrumentation — a
production rejection knows where it came from, because the local audit event
needs that anyway. Nothing test-only is compiled in, and nothing needs to be
enabled for the ordering vectors to work.

`ordering/` therefore has one vector per rejection step, and the assertion is
that a request malformed in a given way rejects at exactly the expected step —
which catches a check that has silently moved earlier or later.

### 4.3 Predicate dispatch

A compiled-in table keyed by `(predicate_id, version)`.

**The registry entry says what a predicate means; the implementation says how it
is computed; the entry's test vectors are what force them to agree.** A predicate
present in the registry with no implementation, or an implementation with no
entry, is a startup failure — not a runtime rejection. A responder that starts
and then cannot serve a predicate it advertises is worse than one that refuses to
start.

**`implementation_digest` stays `null` in MVP, and the reason is worth stating.**
A digest over a Rust binary and a digest over a Go binary are different values
for the same predicate, so no single digest can appear in a shared manifest. The
field becomes meaningful under a verifiable-computation profile, where there is
one canonical program. Until then, **the test vectors are the cross-implementation
pin**, and pretending otherwise by inventing a digest would be worse than leaving
it null.

### 4.4 The evaluation boundary

Predicate code touches private input. Everything crossing back out of it is
therefore a leak risk.

```
evaluate(auth, entry, private_input, public_context)
    -> Result<Output, EvaluationError>
```

**`EvaluationError` is a closed enum with no free-text field and no field capable
of holding a value derived from private input.** Not a string. Not a wrapped
source error. Not an `anyhow`-shaped chain. The type cannot carry the data, so a
careless `format!` has nowhere to put it.

**Panics are caught and their payloads discarded.** A panic message in either
language can carry a formatted value — an index, a slice, a whole struct. The
boundary catches, discards the payload unread, and returns
`EvaluationError::Internal`. Rust: `catch_unwind` with the payload dropped
without inspection. Go: `recover()` with the value not logged.

Discarding a panic payload loses debugging information. That is the trade, made
deliberately: the local audit event records that a predicate faulted and which
one, which is what an operator needs, without the value that faulted it.

### 4.5 Output validation, and what its failure means

After evaluation, the output is validated against **two** things
([`core-model.md`](../../spec/core-model.md) §4 step 17): the effective domain —
shape, membership, cardinality, precision, field allowlist — and the registry
entry's `output_schema`.

The second is not a restatement of the first, which is why step 17 names both.
The domain bounds which values may be returned; the schema bounds how long they
may be. An `attribute` is released in full and permits no narrowing
([`core-model.md`](../../spec/core-model.md) §3.2), so nothing but the schema
bounds it. A value exceeding its bound **fails closed and is never truncated** —
truncation would silently modify an answer the requester treats as complete.

This row previously read *"serialized size"*, following Q2D-C-03, and nothing
carried such a bound. [E-28](../open-escalations.md) resolved it by making the
`output_schema` every entry already carries the mechanism, and
[`scope.md`](../../spec/scope.md) §4.1 now requires that schema to bound every
variable-length value it can release.

A violation is **an implementation or integrity error, not a policy outcome**
([`core-model.md`](../../spec/core-model.md) §4). Concretely:

- it is logged at the highest severity the deployment has, because it means a
  predicate implementation disagrees with its registry entry;
- it rejects, under Tier C like every other post-resolution failure, so the
  requester learns nothing;
- **it does not debit.** [P-008](P-008-capacity-accounting.md) §4.2 puts the
  debit at step 18, after validation, precisely so a result that was never
  released costs nothing;
- the reservation is released.

The asymmetry is deliberate: externally indistinguishable, internally an alarm.

### 4.6 Answer construction

On success the pipeline assembles: the validated result, the effective contract
digest, the assurance profile actually used, the receipt from
[P-011](P-011-receipts-audit.md), and the response signature from
[P-003](P-003-crypto-suites.md).

**Every outcome carries a receipt, not only an answer.** A `deny` and an
explicit `escalate` carry the reduced shape
([`core-model.md`](../../spec/core-model.md) §5.2, §5.3), so step 19 runs on
every path that reached a decision rather than only on the success path. An
*opaque* escalation's receipt is the ordinary deny receipt — the pipeline passes
[P-009](P-009-denial-normalization.md)'s visibility verdict to the receipt
builder, never the internal reason, so there is no path by which an opaque
escalation reaches `decision_class: escalate`
([P-011](P-011-receipts-audit.md) §4.1).

**No field of the answer is derived from private input except the validated
result itself.** Not a timestamp taken from a record, not a count, not an
identifier. Q2D-C-04 is exactly this, and the answer builder is where it is kept
true.

### 4.7 What happens on partial failure

Per [`AGENTS.md`](../../AGENTS.md)'s fifth domain, each interruption is answered
here rather than discovered later.

| Interrupted after | State | Resolution |
|---|---|---|
| Budget reserved, evaluation faults | Reservation held | Released at §4.5; expires anyway at `expires_at + skew`, which is [`freshness.md`](../../spec/freshness.md) §1's skew and the same instant a replay-cache entry is retained to |
| Evaluated, validation fails | Nothing debited | Reservation released; the request becomes a Tier C denial and **carries the reduced receipt like any other denial** ([P-011](P-011-receipts-audit.md) §4.1) — the exchange happened and Q2D-C-10 binds it, whatever the internal cause |
| Validated, signing fails | Nothing debited, nothing cached | Reservation released; request fails; a retry is a fresh exchange |
| Signed, cache write fails | Debit and cache commit atomically ([P-004](P-004-replay-idempotency.md) §4.6) | Both or neither |

Every row leaves the system **more restrictive**, never more permissive. A
crashed exchange costs the requester its request, not the custodian its budget
accounting.

## 5. Interfaces

```
process(envelope: bytes, deps: Responder) -> Response

// internal, in order
step_01_parse_envelope   … step_09_replay_check
step_10_resolve          … step_15_budget_check  -> PrivateAccessAuthorized
step_16_evaluate(auth)   -> Result<Output, EvaluationError>
step_17_validate_output  -> Result<Validated, ValidationError>
step_18_debit                     // staged in the transaction, not yet durable
step_19_receipt_and_sign          // runs for answer, deny, and escalate alike
// the transaction opened at 18 commits once 19 has produced the signed bytes
```

**Steps 15 and 18 are no-ops in this release, and the steps stay.** Q2D-C-09 is
**not attempted** ([`claims.md`](../../spec/claims.md)), so there is no budget to
check at 15 or debit at 18. They keep their places in the orchestration and do
nothing — the same treatment [P-017](P-017-mcp-binding.md) §4.7 gives step 7,
delegation, under the configured-key-list profile.

**Not removed, and not renumbered.** [`core-model.md`](../../spec/core-model.md)
§4's processing order is the specification's, changing it is an escalation, and
§4's numbers are cited across this repository. A step that does nothing under a
profile is not a change to the order; a step that has moved is.

**What still happens at 15 and 18.** Step 15 still mints
`PrivateAccessAuthorized` — the capability token is what makes step 16
unreachable without passing everything above it, and that property is
independent of what step 15 checks. Step 18 still opens the transaction that
step 19's bytes commit into, for the replay-cache entry; what it no longer stages
is a capacity debit.

**The quota tick is not in that transaction, and must not be.** An earlier draft
of this paragraph said the cache entry and the quota tick commit together, which
inverts what the quota is for.
[`core-model.md`](../../spec/core-model.md) §9.1 counts the request at **step
9a** — it counts *authenticated requests*, not successful ones — and a tick that
rolled back when a later step failed would make every failing path free. An
attacker probing with requests that fail output validation would consume no
quota at all, which is precisely the unbounded probing E-01 introduced the limit
to close.

So: **counted at 9a, never rolled back, whatever happens afterwards.** The
transaction at 18–19 governs the cache entry, and a capacity debit if one ever
exists again.

**The transaction spans steps 18 and 19, and this is easy to get wrong.**
[P-004](P-004-replay-idempotency.md) §4.6 requires the debit and the replay-cache
entry to commit atomically, and the cache entry stores the **verbatim response
bytes** — which do not exist until step 19 has signed them. So step 18 does not
write through: it opens the transaction and stages the debit, step 19 produces
the bytes, and the commit is the last act of the exchange.

Three things commit together or none do: the **debit**, the **consumption of a
single-use escalation grant** ([`core-model.md`](../../spec/core-model.md) §5.3),
and the **cache entry with its response bytes**. Committing the debit at step 18
and the cache at step 19 is the "debit, then cache" row of
[P-004](P-004-replay-idempotency.md) §4.6's table — a crash between them
over-charges — and committing in the other order under-charges, which is worse.

The reservation taken at step 15 is what holds capacity across that span, and it
is released rather than settled on any failure before the commit (§4.5).

Consuming the grant earlier — at step 14, where policy *reads* it — would spend a
person's approval on an exchange that then failed output validation.

The rate limit ([`core-model.md`](../../spec/core-model.md) §9.1) is **not** part
of this. It is checked much earlier, at **step 9a**, before registry resolution:
it is keyed on the relationship alone, and a limiter that ran at step 15 would
count only requests that had resolved a predicate, leaving unknown predicates
unlimited — a difference a requester can measure, and therefore the existence
oracle step 10's uniform failure exists to prevent.

`Responder` carries the dependencies each step needs — registry, policy engine,
budget store, replay cache, keys. It is constructed once at startup, so a step
cannot acquire a dependency mid-request and therefore cannot make a network call
the design does not have.

## 6. Corpus sections

| Section | Owner | Content |
|---|---|---|
| `ordering/` | this PRD, **partly landed** | One vector per rejection step, **1–14** plus 5a, 9a and 11a. **Step 15 gets none in this release**: its only rejection cause was budget exhaustion, and Q2D-C-09 is not attempted — the step still runs and still mints the capability, but it has nothing to refuse, so no vector can assert a rejection there. [P-001](P-001-conformance-corpus.md) issue 14 authored steps 1, 3, 4, 5, 5a and 6, so the ordering they establish exists before this PRD is built rather than after. The section stops at 7 because a vector asserting rejection at step N must **pass** steps 1 to N-1, and delegation verification needs a fixture [P-014](P-014-identity-pairing.md) has not defined — so step 8 and steps 10 to 13 are unauthorable despite their own defects being expressible. Issue 11 here adds everything from 7 onward. Step 2 gets none: §4 makes it optional and never a security decision |
| `evaluate/` | this PRD | The three predicates against `registry/manifest.json`'s vectors, run through the full pipeline |
| `validate/` | this PRD | Out-of-domain output; oversized output; cardinality and precision violations |
| `pipeline/` | this PRD | End-to-end answer; end-to-end denial; end-to-end escalation in both modes; partial-failure cases from §4.7 |
| `pipeline/receipt/` | this PRD | Step 19 runs for every outcome — an answer, a denial, and an explicit escalation each carry a receipt; an opaque escalation's is indistinguishable from a denial's |

`evaluate/` is the fold-in [P-001](P-001-conformance-corpus.md) §5 anticipated:
the registry's fourteen vectors already pin predicate behaviour, and here they
run through the whole responder rather than against a reference function.

## 7. Acceptance

- [ ] **No call site can read private input without a `PrivateAccessAuthorized`**,
      and the token has no public constructor. Asserted by the type, not a test.
- [ ] Every `ordering/` vector rejects at exactly its expected step, in both
      implementations.
- [ ] All fourteen registry vectors pass through the full pipeline with the same
      results `registry/validate.py` produces.
- [ ] An out-of-domain output rejects, logs at highest severity, and **does not
      debit**.
- [ ] A predicate panic returns `EvaluationError::Internal` with no payload
      retained, in both languages.
- [ ] Every §4.7 partial-failure row leaves the system no more permissive.
- [ ] **Every outcome carries a receipt.** ~~and an opaque escalation's is
      byte-identical to a plain Tier C denial's~~ — **struck 2026-08-19** with the
      escalation lifecycle.
- [ ] ~~A single-use grant is consumed at step 18 and not before: an exchange that
      fails output validation leaves the grant unconsumed and available.~~
      **Struck 2026-08-19** — grants are P-015's, deferred.
- [ ] A registry entry without an implementation, or an implementation without an
      entry, fails at **startup**.

## 8. Negative acceptance

| Must fail | Observed as |
|---|---|
| Private input read before step 16 | No `PrivateAccessAuthorized` available; does not compile |
| A private value in an error | `EvaluationError` has no field that could hold one |
| A panic payload surviving the boundary | Payload inspected or logged anywhere |
| Out-of-domain output released | `validate/` vector returns an answer |
| ~~Out-of-domain output debiting~~ | **Struck 2026-08-20.** The property was *a validation failure must not debit*, which is Q2D-C-09's and is not attempted. **The quota is not its analogue**: it is counted at step 9a and deliberately never rolled back (§9.1), so a validation failure leaves the tick standing by design. And §4.7 caches every outcome from step 9 onward, so it leaves a cache entry by design too. A retarget of this row in the previous commit asserted the opposite of both and was wrong |
| A step silently reordered | `ordering/` vector rejects at a different step |
| An answer field derived from private input other than the result | Review of the answer builder; no test can catch this |
| A predicate disagreeing with its registry entry | `evaluate/` vector produces a different result |
| A responder starting with a predicate it cannot serve | Startup succeeds with a missing implementation |
| A dependency acquired mid-request | `Responder` is constructed at startup; no step takes a constructor |

Row 7 is honest about a limit. That every answer field except the result is
independent of private input is a property of how the builder is written, and no
vector detects a violation — it needs review, and it is why the answer builder
should be a small, readable function rather than a convenient one.

## 9. Escalate-if-changed decisions

1. **`PrivateAccessAuthorized` is mintable only by the budget check** and has no
   public constructor.
2. **`EvaluationError` carries no free text and no private-derived field.**
3. **Panic payloads are discarded unread** at the evaluation boundary.
4. **Output validation failure is an integrity error**: alarmed internally,
   indistinguishable externally, never debited.
5. **A missing predicate implementation fails at startup**, not per request.
6. **`implementation_digest` stays null in MVP**, because no single digest can
   describe two binaries.
7. **`Responder` is constructed once**, so no step can acquire a dependency
   mid-request.

## 10. Open questions

| Question | Belongs to |
|---|---|
| **Two identical requests in flight at once.** [P-004](P-004-replay-idempotency.md)'s `check` and `record` are separate calls with no state between them, so two copies of one request arriving together both read `Fresh`, both evaluate, and both settle their own reservation — two debits for one exchange, and `core-model.md` §7's idempotent retry not holding. [P-008](P-008-capacity-accounting.md) §4.5 answers only the budget half: reservations keep the *total* inside the limit and say nothing about one exchange being paid for twice. P-004 §10's multi-instance row is a different question, answered *single instance*, which does not help — one daemon serves concurrent requests. The candidates are an in-flight marker in the replay cache or per-key serialization here, and it is here because a vector cannot show it and the pipeline is what would serialize. **Delegated by [P-004](P-004-replay-idempotency.md) §10**, raised by review of its issue 5. Per-key serialization lands in §4.7 and issue 10, which is where every other interruption state is enumerated; an in-flight marker instead would be a **new issue in [P-004](P-004-replay-idempotency.md)**, since the marker would live in its cache. Which of the two it is, is the question | This PRD, issue 10 — or a new P-004 issue, depending on the answer |
| ~~Do predicates run in-process, or in a constrained subprocess?~~ | **Resolved: in-process for MVP.** The three registered predicates are code in this repository operating on fixture data; they execute nothing a requester supplies. A subprocess would bound a faulting predicate, but the IPC boundary would carry private input across it and would itself have to be shown not to leak — a new surface bought to contain a fault that panic-catching already contains (§4.4). **Revisit the moment a predicate evaluates anything untrusted**, which is a change of kind rather than of scale |
| ~~Should evaluation carry a timeout, and does a timeout debit?~~ | **Resolved: yes to the timeout, no to the debit.** A predicate that does not return holds a budget reservation and a replay-cache slot indefinitely, so the timeout is what bounds a hang into a denial. It does not debit for §4.5's reason — the debit is at step 18, after validation, and a result that was never produced was never released. A timeout is a Tier C denial like every other post-resolution failure, and its duration is configuration, not per-predicate, so the elapsed time discloses nothing about which predicate ran |
| ~~Does the step recorder appear in the external response?~~ | **Resolved: no** — audit-only, confirmed. A per-step record on the wire would tell a requester exactly which of §4's nineteen steps rejected, which is the oracle [P-009](P-009-denial-normalization.md)'s tiers exist to close, stated in the most granular form available |
| ~~Where do a predicate's private inputs come from — a fixture store in MVP, or a real adapter?~~ | **Resolved: a fixture store, behind the adapter interface a real source would implement.** The interface is defined now so that a real source is a substitution rather than a redesign, and so the corpus can pin predicate behaviour against known inputs ([`registry/validate.py`](../../registry/validate.py)'s vectors fold in here). Fixtures are synthetic and obviously fictional ([P-016](P-016-demonstration-adversarial.md) issue 1); no real personal data enters this repository |

## 11. Issues

| # | Issue | Done when |
|---|---|---|
| 1 | `PrivateAccessAuthorized` capability type | No public constructor; step 16 is the only consumer |
| 2 | Step orchestration, 1–19 **including 5a, 9a and 11a** | `pipeline/` end-to-end vectors pass |
| 3 | Step recorder in the rejection value | `ordering/` passes; step never reaches the wire |
| 4 | Predicate dispatch table and startup consistency check | Missing implementation or entry fails at startup |
| 5 | Private-input adapter interface plus a fixture store | Open question 4 resolved |
| 6 | `evaluate` with the error boundary and panic catching | Panic returns `Internal`; no payload retained; open question 2 resolved |
| 7 | The three predicate implementations | All fourteen registry vectors pass through the pipeline |
| 8 | `validate_output` against the effective domain and the entry's `output_schema` | `validate/` passes; no debit on failure; a value inside the domain but over its schema bound fails closed, and one inside the schema but outside the domain fails closed — [`core-model.md`](../../spec/core-model.md) §4 step 17. The first is `conformance/over-schema-bound-result`, named in [`claims.md`](../../spec/claims.md) Q2D-C-03 |
| 9 | Answer construction | No field private-derived except the result |
| 10 | Partial-failure handling for §4.7 | Each row leaves the system no more permissive |
| 11 | Author `ordering/` **from step 7 onward** — 7, 8, 9, 9a, 10, 11, 11a, 12, 13, 14 — **not 15**, whose only rejection cause was exhaustion (2026-08-19) — plus `evaluate/`, `validate/`, `pipeline/` | `harness lint` clean; `ordering/` covers every rejection step §4 has except 2, which gets none by design, and `test_ordering_section.py`'s `FIRST_UNPASSABLE_STEP` has been raised past 15 |

Issue 1 blocks 2 and 6. Issue 7 is the least interesting and the most reassuring:
if the fourteen vectors pass through the pipeline exactly as they pass against the
reference function, the nine modules beneath compose correctly.
