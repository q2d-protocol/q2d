# P-009 — Denial normalization

| Field | Detail |
|---|---|
| PRD | P-009 |
| Stage | 3 — closes it |
| Status | **Ready for decomposition** |
| Size | M |
| Risk | medium |
| Depends on | [P-001](P-001-conformance-corpus.md), [P-007](P-007-policy-engine.md) |
| Blocks | P-010, P-013, P-014, P-015, P-016 |
| Pairs with | [P-007](P-007-policy-engine.md) — P-007 separates the audit reason from the external class; this PRD is what stops the reason reaching the wire |


> **Shrunk 2026-08-19 — scope reduction.**
>
> Q2D-C-08 reduces to **one refusal shape, no cause-specific text** — the part
> that is true, testable and cheap. [`terminology.md`](../../spec/terminology.md)
> §9 already forbade claiming the stronger property, and
> [`claims.md`](../../spec/claims.md) Q2D-NC-05 already conceded that timing, size
> and notification channels remain.
>
> **Kept:** the closed `InternalReason` enum, `classify`, `external_class`,
> `build_denial`, the corpus section, the documentation audit — and issue 6,
> **repurposed** from *Tier C uniformity* to **one refusal shape across every
> cause**, asserted across causes rather than per cause. That is now the only
> demonstration Q2D-C-08 has.
>
> **Cut:** Tier B uniformity, the `escalation_visible` gate and the escalate
> receipt split (both belong to the deferred escalation lifecycle), and the timing
> padding hook — whose only consumer was the measurement work, also cut.

---

## 1. Purpose

Map internal outcomes to external classes, and guarantee that every outcome
sharing a class is indistinguishable in the response.

Neither this module nor [P-007](P-007-policy-engine.md) is sufficient alone. P-007
keeps `audit.reason` and `external` in separate fields; this PRD ensures only one
of them can reach a response. The corpus tests the seam rather than either side.

**Claims served:** Q2D-C-08 (denial normalization) directly — and Q2D-NC-05 is
equally load-bearing here, because it is what keeps the claim honest about
timing.

## 2. Spec citations

| Source | What it constrains here |
|---|---|
| [`spec/core-model.md`](../../spec/core-model.md) §5.2 | The `deny` shape; what must be identical across causes; no cause-specific retry guidance |
| [`spec/core-model.md`](../../spec/core-model.md) §5.3 | Explicit escalation is a deliberate disclosure and **must not** be described as normalized |
| [`spec/core-model.md`](../../spec/core-model.md) §4 | The invariant that the external response must not reveal which step failed |
| [`spec/claims.md`](../../spec/claims.md) Q2D-C-08 | What normalization achieves, and where it fails |
| [`spec/claims.md`](../../spec/claims.md) Q2D-NC-05 | Wire-level indistinguishability is **not** claimed |
| [`spec/terminology.md`](../../spec/terminology.md) §6 | Denial normalization; explicit and opaque escalation |
| [`threat-model/trust-matrix.md`](../../threat-model/trust-matrix.md) §5 | Timing, size, and state channels named as residual |
| [`registry/manifest.json`](../../registry/manifest.json) | `denial_normalization` — the reference registry's declared external class, which is Tier C's value only; Tiers A and B are [`core-model.md`](../../spec/core-model.md) §5.2.1's |

## 3. Module boundary

**Inside:** the tier model; the external-class vocabulary; response construction
for a rejection; the uniformity guarantee; the explicit-escalation gate; the
timing hook.

**Explicitly outside:** deciding the outcome (**P-007**). The escalation
lifecycle, pending tokens, and approval-scope digests (**P-015**) — this PRD only
decides whether an escalation is *visible*. Audit writing (**P-011**). Transport
(**P-013**).

## 4. Design

### 4.1 Three tiers, not two

A single normalized class for everything would be simpler and wrong: a malformed
envelope and a policy denial are not the same kind of event, and collapsing them
makes a protocol undebuggable for no privacy gain.

| Tier | Covers | Externally |
|---|---|---|
| **A — protocol** | Malformed or oversized envelope, unknown `q2d_version`, unregistered or unacceptable suite, `routing`/`signed` mismatch, request expired, future-dated, or carrying a validity window outside [`freshness.md`](../../spec/freshness.md) §2's range, **a message that parses and is wrong in a way that is neither a parse failure nor an authentication one** | **Distinct errors** — the six values [`core-model.md`](../../spec/core-model.md) §5.2.1 enumerates |
| **B — authentication** | Unresolvable key, invalid signature, invalid or expired delegation | **One class** — `unauthenticated` (§5.2.1) |
| **C — everything from registry resolution onward** | Unknown predicate or version, revoked or deprecated entry, entry-digest mismatch, schema violation, constraint violation, contract not narrowable, unsupported assurance profile, policy denial, budget exhaustion, source freshness unmet, data absent, internal escalation | **One class** — the value the responder's pinned registry declares (§5.2.1) |
| **C, reached earlier** | **Replay-cache rejection** at step 9, and **rate-limit rejection** ([`core-model.md`](../../spec/core-model.md) §9.1) at step 9a — both before resolution, so the sensitivity class is unknown and the **registry-declared** value is used — a manifest-level declaration rather than an entry's, so it is in hand before anything resolves. It must be the same value an unknown predicate produces at step 10, or the earlier check reveals that resolution was never reached. A replay is normalized rather than distinct because [P-004](P-004-replay-idempotency.md) already makes a cache *failure* Tier C, and distinguishing the two would report whether the custodian's cache is healthy | **Same class** |

The boundaries are drawn by **what each reveals about the custodian**:

- **Tier A reveals nothing about the custodian.** It describes the request. A
  requester learning its envelope was malformed learns about its own bytes.
- **Tier B must be uniform internally**, because distinguishing "key unknown"
  from "signature invalid" tells a requester whether its key is known to this
  custodian — which is relationship existence. This is
  [P-003](P-003-crypto-suites.md) §4.6's requirement, and this PRD is where it is
  enforced.
- **Tier C must be uniform internally**, because *any* distinction within it
  reveals custodian-private state. Including schema violations: a precise schema
  error confirms the predicate is supported by this custodian, and which entries
  a custodian accepts is policy.

A, B, and C are distinguishable **from each other**. A requester that
authenticates successfully already knows its own key works, so learning it
reached Tier C tells it nothing it did not have.

### 4.2 Request expiry and source freshness are different tiers

Easy to conflate, and they land on opposite sides.

**Request expiry** — `expires_at` passed — is Tier A. It is a property of the
request, evaluated at step 6, and reveals nothing.

**Source freshness** — the custodian's data is older than
`freshness.maximum_source_age` — is Tier C. It is a fact about the custodian's
data, and a requester learning it learns when that data was last updated.

[`core-model.md`](../../spec/core-model.md) §5.2's list says "failed freshness",
meaning the second.

### 4.3 Uniformity is structural, not enforced

The `deny` response carries a request digest, a decision class, a decision time,
and a signature. **None of these is variable-length**: SHA-256 is 32 bytes, the
class is a fixed enum value, a timestamp is fixed width because
[`core-model.md`](../../spec/core-model.md) §2.2 permits one spelling of it —
`+00:00` would be six characters where `Z` is one — Ed25519 is
64 bytes.

So byte-length uniformity falls out of the shape rather than needing to be
policed — provided nothing variable-length is ever added. Adding an optional
field to a denial is therefore an escalation, not a feature: one optional field
present for some causes and absent for others reintroduces the distinction the
tier exists to remove.

**The receipt is inside this guarantee, not beside it.** A `deny` carries the
reduced receipt ([P-011](P-011-receipts-audit.md) §4.1), and so does an *opaque*
escalation — the same fields, the same `decision_class`, the same bytes. Only an
**explicit** escalation carries `decision_class: escalate`, and explicit
escalation is not in a normalized class
([`core-model.md`](../../spec/core-model.md) §5.3).

This is the boundary worth stating twice. A receipt that recorded `escalate` for
an opaque escalation would defeat this whole PRD through the evidence attached to
the response, in the one place nobody thinks to look for a normalization leak —
the uniformity assertion would still pass on the response body while the
exchange was fully distinguishable.

### 4.4 No retry metadata

MVP emits none.

[`core-model.md`](../../spec/core-model.md) §5.2 **has no field for retry
metadata**, so this is now structural rather than a module decision. It was a
module decision first: §5.2 used to permit retry metadata whose value was
identical across every cause, this PRD declined to emit any, and the argument
was that meeting the uniformity condition is possible and is a standing
invitation to get it wrong — a `Retry-After` computed from a rate limiter is
cause-specific by construction, and it would take one plausible commit to
introduce. That argument closed the permission rather than merely declining it.

Emitting none costs a requester a backoff hint it can supply itself.

**This stopped being hypothetical.** [`core-model.md`](../../spec/core-model.md)
§9.1 makes a rate limiter a required part of a conforming responder — it is what
bounds the probing that denials no longer debit for. So the module most likely to
produce cause-specific retry metadata is now one every deployment runs, and its
rejection is a Tier C cause like any other. A rate limiter that answers "try
again in 40 seconds" has partitioned the class by cause, and the fact that it was
introduced to close an oracle makes it no less of one.

The rule is unchanged and now structural: **no retry metadata, from any source,
for any cause.** [`core-model.md`](../../spec/core-model.md) §5.2 carries it in
the response — there is no field to put a value in —
and [P-013](P-013-https-binding.md) §4.2 carries the transport half: no `429`,
no `503`, no `Retry-After` header.

### 4.5 The wire builder cannot see the reason

```
build_denial(external: ExternalClass, request_digest, now) -> DenyResponse
```

It takes the external class, **not** the `Decision`. There is no parameter
through which `audit.reason` could arrive, so the leak requires changing a
signature rather than making a mistake.

This is the seam [P-007](P-007-policy-engine.md) §4.3 sets up. P-007 populates
two fields separately; this signature makes only one of them reachable.

### 4.6 Explicit escalation is the one legitimate distinction

An `escalate` outcome becomes a **visible** response only when the sensitivity
class explicitly permits it. Otherwise it returns the Tier C class, and the
authority is prompted out of band.

[`core-model.md`](../../spec/core-model.md) §5.3 is emphatic that explicit
escalation is a deliberate disclosure — it reveals that a relationship, record,
or applicable policy path may exist — and **must never be described as
denial-normalized**.

So the gate is a policy input, defaulting to opaque. A deployment choosing
explicit escalation is choosing to disclose, and should have to say so.

### 4.7 Timing: not normalized, and named

MVP does **not** normalize timing. Q2D-NC-05 already scopes the claim, and
[`trust-matrix.md`](../../threat-model/trust-matrix.md) §5 names timing among the
residual channels.

Two things this PRD does anyway:

**No gratuitous timing differences.** A Tier C rejection at step 10 completes far
sooner than one at step 14. That difference is inherent to fail-fast ordering and
is not worth surrendering — checking cheaply before expensively is the right
design. But the module must not *add* to it: no cause-specific logging volume, no
cause-specific retry sleep, no expensive formatting on one branch only.

**A padding hook, default off.** A configurable minimum response time for Tier C,
so fast rejections pad to the slowest. Default off, because enabling it costs
latency on every rejection and the claim does not depend on it. Present so Stage
8 can measure the difference rather than needing to build the mechanism first.

Documentation must not describe MVP as timing-normalized. It is not.

## 5. Interfaces

```
classify(internal: InternalReason) -> Tier
external_class(tier: Tier, sensitivity: SensitivityClass) -> ExternalClass
build_denial(external: ExternalClass, request_digest, now) -> DenyResponse
escalation_visible(sensitivity: SensitivityClass, policy) -> bool
```

`ExternalClass` is [`core-model.md`](../../spec/core-model.md) §5.2.1's closed
vocabulary — six Tier A values, `unauthenticated` for Tier B, and for Tier C
whatever the responder's **pinned registry** declares, which is a manifest-level
value rather than an entry's. That matters here because `external_class` is
called for rejections that never resolve an entry: a replay at step 9, a rate
limit at 9a, an unknown predicate at 10. It is not this module's to extend:
adding a value is a `spec/` change, because a requester acts on it and one
deployment inventing a name makes that value meaningless everywhere else.

`classify` is total over a **closed** `InternalReason` enum. A new internal
reason must be assigned a tier at the point it is added, and an unassigned reason
is a compile error rather than a runtime default — a default would silently place
a new failure mode in whichever tier the fallback names.

## 6. Corpus sections

`denial/` — authored under this PRD.

| Group | Vectors |
|---|---|
| `denial/tiers/` | Every `InternalReason`, asserting its tier |
| `denial/uniformity-b/` | Every Tier B cause produces a byte-identical response |
| `denial/uniformity-c/` | Every Tier C cause produces a byte-identical response |
| `denial/tier-a/` | Protocol errors are distinct and informative |
| `denial/escalation/` | Opaque by default; visible only where the class permits |
| `denial/no-retry/` | No retry metadata on any denial, including a rate-limit rejection |
| `denial/receipt-uniformity/` | The reduced receipt is byte-identical across every Tier C cause, and an **opaque** escalation's receipt is indistinguishable from a plain denial's — only an explicit escalation carries `decision_class: escalate` |

`denial/uniformity-b/` and `denial/uniformity-c/` are the P-001 cross-vector
denial-uniformity assertion applied to this module — the same check
[`registry/validate.py`](../../registry/validate.py) already performs over
registry rejections.

**Every vector in this section asserts the whole response**, meaning
[`core-model.md`](../../spec/core-model.md) §5.2's four fields including the
reduced receipt — not a projection of them.
[`conformance/vector.schema.json`](../../conformance/vector.schema.json) states
that rule on `wire`, and it is not a formality here: `status` and
`external_reason` are both fixed by the normalized class, so a vector asserting
only those two compares two constants and cannot fail. §7's requirement that
*"the receipt attached to a Tier C denial is byte-identical across causes"*
is unverifiable by a vector that omits the receipt, and §5.3 puts the leak
exactly there — *"in the one place nobody looks for a normalization leak."*

**§7 says two things about this and they do not agree.** Its first line allows a
Tier C response to differ *"only in `request_digest` and `decided_at`"*; its
receipt line asks for byte-identity with no such carve-out. Both are satisfiable
in the corpus, where §4.3 requires every varying input to come from the vector,
so two causes over one request share a digest and a decision time and the
receipts are identical outright. They are not both satisfiable in production,
where two exchanges differ in exactly those two fields. **Which one §7 means is
a question for this PRD**, and the corpus enforces the achievable reading
meanwhile: identical, because the vector fixes both fields.

**Nothing now blocks authoring these vectors.** A signature is producible
([`crypto-suites.md`](../../spec/crypto-suites.md) §3 defines the protected
header), §5.2's field list is closed at four, and
[`core-model.md`](../../spec/core-model.md) §2.2 fixes one timestamp spelling —
which together mean the bytes of a whole-response denial vector are determined
rather than chosen.

Meanwhile the corpus's existing rejection vectors assert projections, and the
harness names every one of them on every run, so nothing reads a partial
comparison as uniformity.

## 7. Acceptance

- [ ] Every Tier C cause produces a **byte-identical** response in both
      implementations, differing only in `request_digest` and `decided_at`.
- [ ] Every Tier B cause likewise.
- [ ] Response length is constant within a tier, across all causes.
- [ ] `classify` is total; adding an `InternalReason` without a tier fails to
      compile.
- [ ] Escalation is opaque unless the sensitivity class permits visibility.
- [ ] **The receipt attached to a Tier C denial is byte-identical across causes**,
      and an opaque escalation's receipt is indistinguishable from a plain
      denial's.
- [ ] A rate-limit rejection is one Tier C cause among the others, with no
      distinguishing field, header, or timing treatment.
- [ ] No denial carries retry metadata.
- [ ] Documentation and code comments describe MVP as **not** timing-normalized.

## 8. Negative acceptance

| Must fail | Observed as |
|---|---|
| Two Tier C causes producing different bytes | Cross-vector uniformity assertion fails |
| Two Tier B causes distinguishable | Same, for Tier B |
| Response length varying with cause | Length comparison across `denial/uniformity-*/` |
| `audit.reason` reaching a response | `build_denial` has no parameter it could arrive through |
| An optional field on a denial present for some causes | Length varies; uniformity fails |
| Explicit escalation where the class forbids it | `denial/escalation/` returns a visible response |
| A new `InternalReason` defaulting to a tier | Compile failure absent; a default branch exists |
| Retry metadata appearing | `denial/no-retry/` fails |
| A rate-limit rejection distinguishable from any other Tier C cause | `denial/uniformity-c/` fails once the rate-limit cause is in its input set |
| **An opaque escalation's receipt carrying `decision_class: escalate`** | `denial/receipt-uniformity/` fails; the response bodies still match, which is why the receipt needs its own vector |
| A claim of timing normalization | Grep for the phrase in docs and comments |

Row 4 is the one this module exists for, and it is enforced by a signature rather
than a test — the leak requires someone to widen an interface deliberately.

Row 7 matters more than it reads. A `_ => Tier::C` fallback looks safe and is
not: a new failure mode that should have been Tier A becomes silently opaque, or
one that should have been Tier C becomes silently distinct.

## 9. Escalate-if-changed decisions

1. **Three tiers, with the boundaries in §4.1.** Drawn by what each reveals about
   the custodian, not by convenience.
2. **Tier B is internally uniform** — key resolution and signature failure are
   indistinguishable.
3. **Tier C is internally uniform**, including schema violations.
4. **`build_denial` takes only the external class.**
5. **No variable-length field on a denial**, so uniformity stays structural.
6. **No retry metadata**, from any source, including the required rate limiter
   ([`core-model.md`](../../spec/core-model.md) §9.1).
7. **Explicit escalation is policy-gated, defaults to opaque, and is never
   described as normalized.**
8. **The reduced receipt is inside the uniformity guarantee.** Only an explicit
   escalation carries `decision_class: escalate`; an opaque one carries the
   ordinary deny receipt.
9. **`classify` is total with no default branch.**

## 10. Open questions

| Question | Belongs to |
|---|---|
| ~~Should Tier B and Tier C be merged?~~ | **Resolved: keep them separate.** Tier B is authentication failure, which a requester can already determine from its own key material without asking the custodian anything — merging it into Tier C would hide nothing it does not already know while making every signature bug indistinguishable from a policy denial in the operator's own logs. The tiers are internally uniform, which is the property that matters; the boundary between them discloses nothing |
| ~~Is one Tier C class enough, or should sensitivity classes have their own?~~ | **Resolved: one.** A per-sensitivity-class external value would partition causes by sensitivity class, which is a property of the *predicate* — so the external value would tell a requester which class its predicate falls in, reintroducing at the class level exactly the oracle uniformity closes at the cause level |
| ~~Does the padding hook belong in this module or the binding?~~ | **Answered:** here. [P-013](P-013-https-binding.md) §3 confirms the binding adds none of its own |
| ~~Should `decided_at` be coarsened — minute rather than second — to blunt timing correlation?~~ | **Resolved: no in MVP**, at second precision. Coarsening it would blunt nothing an observer cannot measure directly from arrival time, while interacting badly with the replay window and clock-skew arithmetic in [`freshness.md`](../../spec/freshness.md) §2 — that arithmetic is exact at its boundaries, and a minute-coarsened field lands on one of them sixty times more often than a second-precision field does. Timing is a named residual channel ([`trust-matrix.md`](../../threat-model/trust-matrix.md) §5) and [P-016](P-016-demonstration-adversarial.md) measures it at Stage 8; the same answer covers [P-011](P-011-receipts-audit.md)'s receipt field |

## 11. Issues

| # | Issue | Done when |
|---|---|---|
| 1 | Closed `InternalReason` enum, both languages | Every reason from Stages 1–3 present |
| 2 | `classify`, total, no default branch | Adding a reason without a tier fails to compile |
| 3 | `external_class` and the class vocabulary | Matches `registry/manifest.json`'s `denial_normalization` |
| 4 | `build_denial` with the constrained signature | No path from `Decision` to a response |
| ~~5~~ | ~~Tier B uniformity~~ | **Cut 2026-08-19.** Folded into issue 6 — one uniformity assertion, not one per tier |
| 6 | **Uniformity within a normalized class**, asserted **across causes** | `denial/uniformity/` passes under the cross-vector check; length constant. **Repurposed 2026-08-19** from *Tier C uniformity*: one assertion covering every cause inside a class, rather than one per tier. **This is now the only demonstration Q2D-C-08 has.** Tier A's informative values stay distinct — `core-model.md` §5.2.1 |
| ~~7~~ | ~~`escalation_visible` gate~~ | **Cut 2026-08-19** — separates explicit from opaque escalation, and the lifecycle is deferred with [P-015](P-015-escalation-lifecycle.md) |
| ~~8~~ | ~~Timing padding hook, default off~~ | **Cut 2026-08-19** — shipped default-off and its only consumer was the measurement work, also cut. Q2D-NC-05's concession that timing channels remain is now the whole of what is said |
| 8a | Rate-limit rejection wired in as a Tier C `InternalReason` | Present in `classify`; `denial/uniformity-c/` includes it; no header, field, or retry value distinguishes it |
| ~~8b~~ | ~~Receipt uniformity across Tier C, and the explicit/opaque receipt split~~ | **Cut 2026-08-19** — the split is the escalation lifecycle's. Receipt uniformity across refusal causes rides in issue 6. ~~`denial/receipt-uniformity/` passes |
| 9 | Author `denial/` corpus section | **Five** groups; `harness lint` clean. `uniformity-b/`, `escalation/` and `receipt-uniformity/` go with the cut issues |
| 10 | Documentation audit for timing claims | No artifact describes MVP as timing-normalized |

Issue 1 blocks 2 and 3. Issues 5, 6, and 8b are the ones that matter — they are
the only place Q2D-C-08 is actually demonstrated rather than asserted, and 8b
covers the half of the response that is not the response body.
