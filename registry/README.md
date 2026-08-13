# Q2D reference predicate registry

The registry is what makes a Q2D responder able to say *no*. It is the trusted,
versioned source a custodian resolves a requested predicate against — and the
reason a requester cannot declare its own leakage bound
([`Q2D-C-02`](../spec/claims.md)).

```
manifest.json    the registry itself: three predicates, schemas, domains,
                 capacity calculations, sensitivity, and test vectors
validate.py      internal consistency + executes every test vector
```

```sh
python3 registry/validate.py
```

## Status: unsigned, and therefore untrustworthy

**No deployment may pin this manifest.** Q2D 0.1's bootstrap is a *signed*
manifest whose signing key and digest a custodian pins locally
([`spec/scope.md`](../spec/scope.md) §4). No signing key exists yet, so there is
nothing to pin and nothing to verify.

This file is the shape of a registry and a set of vectors to build against. It
is not yet a trust anchor.

When signing lands, it uses `eddsa-jws-2026` like every other Q2D signature
([`spec/crypto-suites.md`](../spec/crypto-suites.md)), as a detached signature
over the exact bytes of `manifest.json`. The digest a custodian pins is of those
bytes — which is why the manifest cannot contain its own digest.

## What a custodian does with it

1. Pins one or more registry signing keys and the accepted manifest digest.
2. On each request, resolves `predicate.id` + `predicate.version` against the
   pinned manifest.
3. **Fails closed** on an unknown predicate, unknown version, unpinned digest, or
   untrusted signer — before any private data is accessed
   ([`spec/core-model.md`](../spec/core-model.md) §4, step 10).
4. Computes the effective answer domain as the intersection of this entry, the
   requester's answer contract, and policy modifiers.
5. Computes the capacity debit from that effective domain.

A custodian is free not to trust any entry here. **The registry proposes; the
custodian decides.** Two registries disagreeing has no resolution mechanism in
0.1 — the custodian's pinned registry governs, and federation is deferred.

## The three predicates

| Predicate | Shape | Domain | Capacity | Sensitivity |
|---|---|---|---|---|
| `menu_compatible` | `boolean` | 2 | 1 bit | **high** |
| `availability_window` | `interval` | *k*+1, k ≤ 8 | log2(k+1), ≤ 3.17 bits | moderate |
| `contactable_for` | `enum` | 3 | 1.585 bits | moderate |

Each entry carries a `question_notes` field recording *why* the question is
phrased as it is. That reasoning is the most portable thing in the file: a future
predicate author needs the principle more than the schema.

Three examples of the principle at work:

- **`menu_compatible` asks "is any item compatible", not "which items conflict".**
  The second returns a per-item vector that leaks the shape of the constraint
  set. A `false` answer here reveals neither which constraint caused it nor how
  many exist.
- **`availability_window` returns the *first* free slot, not all of them.** The
  requester supplies the candidates, so the domain is bounded by the request and
  the debit scales with it. Returning every free slot would leak the shape of a
  calendar.
- **`contactable_for` returns a permission class, never a contact detail.** A
  requester learns whether it may call. It does not learn a number.

### Capacity is not severity

`menu_compatible` is one bit and classified **high**. Dietary exclusions are a
documented proxy for religious observance and medical conditions — both GDPR
Article 9 special categories. The inference a single bit supports is not
proportionate to its size.

This is the concrete case behind [`Q2D-NC-07`](../spec/claims.md). A registry
that classified sensitivity by answer size would get this exactly backwards, and
the entry says so in its own `rationale` field so no reviewer has to rediscover
it.

### Anti-probing constraints

`availability_window` carries a 30-minute granularity floor and a 14-day
horizon. Neither is a usability limit. Without a floor, an adversary reconstructs
a calendar through repeated narrow candidates, and the capacity budget does not
stop them — each query is individually cheap. **Granularity floors are a
registry-level control that the budget cannot substitute for.**

## Two problems this work surfaced, and how they were resolved

### 1. Capacity is a float — so it is no longer stored as one

`contactable_for` has a three-value domain, so its true debit is
`log2(3) = 1.584962500721156`. An implementation that rounds or truncates that
would disagree with a conforming one on **every** running budget total, and the
disagreement would look like a policy bug rather than an arithmetic one.

Capacity is therefore carried in **millibits** — integers, thousandths of a bit:

```
capacity_millibits = ceil(1000 × log2(cardinality))
```

| cardinality | millibits | over-charge |
|---|---|---|
| 2 | 1000 | 0 |
| 3 | 1585 | +0.000037 bits |
| 7 | 2808 | +0.000645 bits |
| 9 | 3170 | +0.000075 bits |

Integer addition is exact and order-independent, so accumulation cannot drift.
Ceiling rounding means the accounting can over-charge and never under-charge —
the conservative direction — and the worst case across every reachable
cardinality is **0.000645 bits**.

The part that actually closes the hole: **a responder never computes `log2` at
runtime.** IEEE-754 does not require a correctly-rounded `log2`, so two
implementations could differ in the last place, and a rounding boundary would
turn that into a different integer. The value is authored once into the registry
entry; where cardinality varies with the request, the entry carries a lookup
table that is **total** over the values it covers, rather than over the ones a
particular requester is expected to ask for
([`core-model.md`](../spec/core-model.md) §3.2). For an enumerated entry,
`validate.py` fixes that range at two through the registered cardinality. Whether
that is the right range is
[`open-escalations.md`](../docs/open-escalations.md) **E-27**, which is open and
is `spec/`'s to answer; an entry authored today is authored to pass the
validator, and nothing in this file bears on how E-27 should resolve. A locally computed capacity is non-conforming
even when it happens to agree — the same principle as
[`Q2D-C-02`](../spec/claims.md), applied to accounting.

Whole-bit rounding was considered and rejected: it over-charges 26% at
cardinality 3, which is coarse enough to distort the budget as a tuning
parameter. Millibits are precise enough to be honest and coarse enough not to
imply precision the mechanism lacks.

Specified in [`spec/core-model.md`](../spec/core-model.md) §3.1.

### 2. Rejection reasons are an oracle — so the wire carries none

Every rejection vector now records two things: the **internal reason**, which the
local audit event holds, and the **wire response**, which is identical for all of
them:

```json
"internal_reason": "constraint_violation_minimum_slot_duration",
"wire": { "status": "deny", "external_reason": "unavailable" }
```

`validate.py` asserts the cross-vector invariant that per-vector checks cannot
catch: **every rejection returns a byte-identical wire response, while distinct
internal reasons exist behind it.** Five rejections, two internal reasons, one
external response.

The subtle part is why even a *schema* violation must be normalized. A schema is
public — a requester could have predicted the failure — so reporting it appears
to leak nothing. But answering precisely confirms *the predicate is supported by
this custodian*, and which entries a custodian accepts is custodian-private
policy. A custodian that supports a health predicate has said something by
supporting it.

So the safe default is one external class for every rejection. A deployment may
report precisely only where its sensitivity class explicitly permits, and must
then do so uniformly across that class ([`Q2D-C-08`](../spec/claims.md)).

## Adding a predicate

A new entry needs all of:

- a stable URL identifier and a version, **both permanent** — a change of meaning
  requires a new version;
- input, public-context, and output schemas;
- a canonical answer domain, or an expression bounding it;
- a capacity calculation, and a maximum where the domain is computed;
- a sensitivity class with a **written rationale**, including what it proxies for;
- freshness semantics;
- supported assurance profiles;
- provenance and revocation metadata;
- positive **and negative** test vectors, including at least one rejection that
  must occur before private access.

An entry without negative vectors is not reviewable. The interesting property of
a predicate is not what it answers — it is what it refuses.

Review happens through public issues. A predicate that encodes a discriminatory
or unlawful decision is a governance problem the protocol cannot solve, and
review is the only control 0.1 has.

## Deferred

Federation, cross-signing, and precedence between registries. Reproducible
implementation digests. A public transparency log of registry versions. All are
[`spec/scope.md`](../spec/scope.md) §7 items, and all need implementation
experience first.
