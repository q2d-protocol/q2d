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

## Two problems this work surfaced

Both are real, neither is resolved, and both are recorded here rather than
quietly decided.

### 1. Capacity is a float, and floats disagree across languages

`contactable_for` has a three-value domain, so its debit is
`log2(3) = 1.584962500721156` — deliberately non-integral, and deliberately
included as a test vector.

An implementation that rounds, truncates, or stores this as an integer will
disagree with a conforming one on **every** running budget total. Two
implementations built against these vectors will disagree the moment they
accumulate debits, and the disagreement will look like a policy bug rather than
an arithmetic one.

This needs a decision before the budget is implemented:

- fixed-point at a defined precision, or
- IEEE-754 double with a specified accumulation order, or
- store cardinalities and compute in log space only at comparison time.

The third is the most robust and the least convenient. Not decided here —
[`spec/core-model.md`](../spec/core-model.md) §9 is where it lands.

### 2. Rejection reasons are themselves an oracle

The vectors distinguish `public_context_schema_violation` from
`constraint_violation_minimum_slot_duration`. That is correct for a *test*
vector — an implementation must be able to prove it rejected for the right
reason.

It is **wrong on the wire** wherever denial normalization applies
([`Q2D-C-08`](../spec/claims.md)). A requester learning *which* validation failed
learns about the registry entry, and in the granularity-floor case learns that
probing is being actively resisted.

The internal reason and the external class are different values. These vectors
pin the internal one. A conforming responder maps them to a single normalized
external class within a sensitivity class, and the conformance suite must test
both halves — that the right internal reason is recorded, and that it does not
reach the wire.

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
