# P-010 — Responder pipeline, predicate execution, output validation

| Field | Detail |
|---|---|
| PRD | P-010 |
| Stage | 4 |
| Status | **Ready for decomposition** |
| Size | L |
| Risk | medium |
| Depends on | [P-002](P-002-message-envelope.md), [P-003](P-003-crypto-suites.md), [P-004](P-004-replay-idempotency.md), [P-005](P-005-registry-client.md), [P-006](P-006-request-validation.md), [P-007](P-007-policy-engine.md), [P-008](P-008-capacity-accounting.md), [P-009](P-009-denial-normalization.md) — every prior module |
| Blocks | P-011, P-013, P-015 |

---

## 1. Purpose

Orchestrate [`core-model.md`](../../spec/core-model.md) §4's nineteen steps into
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
| [`spec/core-model.md`](../../spec/core-model.md) §4 | The nineteen steps, their order, and the three invariants |
| [`spec/core-model.md`](../../spec/core-model.md) §4 step 17 | Output validation fails closed; the runtime must not serialize an exception carrying private input |
| [`spec/core-model.md`](../../spec/core-model.md) §5.1 | The `answer` response shape |
| [`spec/claims.md`](../../spec/claims.md) Q2D-C-03 | Bounded output, and what it does not claim |
| [`spec/claims.md`](../../spec/claims.md) Q2D-C-04 | Private input is not serialized into the response |
| [`spec/conformance-classes.md`](../../spec/conformance-classes.md) CC-2 | Must not read private input before step 16; must not reorder steps 1–16 |
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

```
PrivateAccessAuthorized     // constructible ONLY by the budget check at step 15
read_private_input(auth: PrivateAccessAuthorized, ...) -> PrivateInput
```

The token has no public constructor. Steps 1–15 produce it or the request is
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

After evaluation, the output is validated against the effective domain: shape,
membership, cardinality, precision, field allowlist, serialized size.

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

**No field of the answer is derived from private input except the validated
result itself.** Not a timestamp taken from a record, not a count, not an
identifier. Q2D-C-04 is exactly this, and the answer builder is where it is kept
true.

### 4.7 What happens on partial failure

Per [`AGENTS.md`](../../AGENTS.md)'s fifth domain, each interruption is answered
here rather than discovered later.

| Interrupted after | State | Resolution |
|---|---|---|
| Budget reserved, evaluation faults | Reservation held | Released at §4.5; expires anyway at `expires_at + skew` |
| Evaluated, validation fails | Nothing debited | Reservation released; no receipt |
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
step_18_debit
step_19_receipt_and_sign
```

`Responder` carries the dependencies each step needs — registry, policy engine,
budget store, replay cache, keys. It is constructed once at startup, so a step
cannot acquire a dependency mid-request and therefore cannot make a network call
the design does not have.

## 6. Corpus sections

| Section | Owner | Content |
|---|---|---|
| `ordering/` | this PRD | One vector per rejection step, 1–15 |
| `evaluate/` | this PRD | The three predicates against `registry/manifest.json`'s vectors, run through the full pipeline |
| `validate/` | this PRD | Out-of-domain output; oversized output; cardinality and precision violations |
| `pipeline/` | this PRD | End-to-end answer; end-to-end denial; partial-failure cases from §4.7 |

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
- [ ] A registry entry without an implementation, or an implementation without an
      entry, fails at **startup**.

## 8. Negative acceptance

| Must fail | Observed as |
|---|---|
| Private input read before step 16 | No `PrivateAccessAuthorized` available; does not compile |
| A private value in an error | `EvaluationError` has no field that could hold one |
| A panic payload surviving the boundary | Payload inspected or logged anywhere |
| Out-of-domain output released | `validate/` vector returns an answer |
| Out-of-domain output debiting | Budget total changes on a validation failure |
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
| Do predicates run in-process, or in a constrained subprocess? Proposed: in-process for MVP. A subprocess bounds a faulting predicate but adds an IPC surface that would itself need to not leak | This PRD; revisit if a predicate ever executes untrusted input |
| Should evaluation carry a timeout, and does a timeout debit? Proposed: yes to the timeout, no to the debit — same reasoning as validation failure | This PRD; blocks issue 6 |
| Does the step recorder appear in the external response? **No** — it is audit-only. Confirming here because it would be a per-step oracle | [P-009](P-009-denial-normalization.md) — already Tier C |
| Where do a predicate's private inputs come from — a fixture store in MVP, or a real adapter? Proposed: fixture store, with the adapter interface defined so a real source is a swap | This PRD; blocks issue 5 |

## 11. Issues

| # | Issue | Done when |
|---|---|---|
| 1 | `PrivateAccessAuthorized` capability type | No public constructor; step 16 is the only consumer |
| 2 | Step orchestration, 1–19 | `pipeline/` end-to-end vectors pass |
| 3 | Step recorder in the rejection value | `ordering/` passes; step never reaches the wire |
| 4 | Predicate dispatch table and startup consistency check | Missing implementation or entry fails at startup |
| 5 | Private-input adapter interface plus a fixture store | Open question 4 resolved |
| 6 | `evaluate` with the error boundary and panic catching | Panic returns `Internal`; no payload retained; open question 2 resolved |
| 7 | The three predicate implementations | All fourteen registry vectors pass through the pipeline |
| 8 | `validate_output` against the effective domain | `validate/` passes; no debit on failure |
| 9 | Answer construction | No field private-derived except the result |
| 10 | Partial-failure handling for §4.7 | Each row leaves the system no more permissive |
| 11 | Author `ordering/`, `evaluate/`, `validate/`, `pipeline/` | Four sections; `harness lint` clean |

Issue 1 blocks 2 and 6. Issue 7 is the least interesting and the most reassuring:
if the fourteen vectors pass through the pipeline exactly as they pass against the
reference function, the nine modules beneath compose correctly.
