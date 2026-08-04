# P-006 — Request validation and effective answer domain

| Field | Detail |
|---|---|
| PRD | P-006 |
| Stage | 2 — closes it |
| Status | **Ready for decomposition** |
| Size | M |
| Risk | medium |
| Depends on | [P-002](P-002-message-envelope.md), [P-005](P-005-registry-client.md) |
| Blocks | P-007, P-008, P-010, P-012 |

---

## 1. Purpose

Validate a request against the registry entry [P-005](P-005-registry-client.md)
resolved, and compute the answer domain that bounds what may be released.

**Claims served:** Q2D-C-02 (responder-owned domain validation) — P-005 obtains
a trusted entry, this PRD is where the entry actually constrains a request.
Q2D-C-03 and Q2D-C-09 both consume its output.

> Authoring this PRD surfaced a leak in a behaviour the specification permitted.
> It was escalated and **resolved as (A)**: coarsening only, subsetting
> prohibited. [`core-model.md`](../../spec/core-model.md) §2.5,
> [`terminology.md`](../../spec/terminology.md) §6, and
> [`claims.md`](../../spec/claims.md) Q2D-C-09 were amended. §4.4 records the
> reasoning.

## 2. Spec citations

| Source | What it constrains here |
|---|---|
| [`spec/core-model.md`](../../spec/core-model.md) §3 | `effective_domain` as an intersection; empty intersection fails closed |
| [`spec/core-model.md`](../../spec/core-model.md) §2.5 | The answer contract; **coarsening only** — never an expansion and never a strict subset |
| [`spec/core-model.md`](../../spec/core-model.md) §4 steps 11–13 | Schema validation, contract narrowing, assurance profile support |
| [`spec/claims.md`](../../spec/claims.md) Q2D-C-02 | The domain is resolved by the responder, never accepted from the requester |
| [`spec/terminology.md`](../../spec/terminology.md) §4 | The eight release shapes |
| [`spec/terminology.md`](../../spec/terminology.md) §6 | Effective answer domain; decision modifiers |
| [`registry/manifest.json`](../../registry/manifest.json) | `public_context_schema`, `answer_domain`, `constraints` |

## 3. Module boundary

**Inside:** public-context schema validation; the JSON Schema profile the
registry may use; per-predicate constraint checks; contract narrowing validation;
domain intersection; assurance-profile support check.

**Explicitly outside:** obtaining the entry (**P-005**). Capacity arithmetic
(**P-008**) — this module produces the domain, P-008 looks up its charge. The
policy decision itself (**P-007**); this module applies modifiers that P-007
returns but never produces one. Output validation against the domain
(**P-010**).

## 4. Design

### 4.1 Three domains, not one

[`core-model.md`](../../spec/core-model.md) §3 states the intersection as one
formula, but §4 evaluates it in two phases either side of the policy call. Naming
the intermediate state prevents the bug where modifiers are forgotten or applied
before the contract is checked.

| Term | Is | Computed at |
|---|---|---|
| **Requested domain** | What the contract asks for | supplied by requester |
| **Admissible domain** | registry ∩ requested | step 12, before policy |
| **Effective domain** | admissible ∩ modifiers | after step 14 |

*Admissible domain* is implementation vocabulary. It is not a wire concept, does
not appear in a receipt, and must not leak into protocol documentation — only
**effective domain** is a Q2D term.

An empty intersection at either phase fails closed.

### 4.2 The JSON Schema profile

Two JSON Schema libraries can disagree on edge cases, and a disagreement here is
a cross-implementation divergence in what counts as a valid request.

The registry may therefore use only this profile, and the validator rejects a
schema using anything outside it:

`type` · `required` · `properties` · `additionalProperties: false` · `enum` ·
`minItems` / `maxItems` · `minLength` / `maxLength` · `minimum` / `maximum` ·
`format: date-time`

No `$ref`, no `oneOf` / `anyOf` / `allOf` / `not`, no `patternProperties`, no
regular expressions, no remote schema resolution. Every current entry in
[`registry/manifest.json`](../../registry/manifest.json) already fits.

Restricting the schema language is cheaper than reconciling two implementations
of all of it, and a predicate needing more expressiveness is a signal the
predicate is too complicated to review.

### 4.3 Constraints are separate from schemas

A registry entry's `constraints` object carries checks JSON Schema cannot
express — `minimum_slot_duration` and `maximum_horizon` on
`availability_window` are the current two. They are anti-probing controls, not
usability limits, and are evaluated after schema validation and before private
access.

The constraint vocabulary is **closed**. Adding one is a registry format change,
not a client change, so the two implementations cannot drift on what a constraint
means.

### 4.4 Escalation: narrowing an enumerated domain is a free oracle

*Recorded as it was found. §2.5 has since been amended — see the resolution at
the end of this section.*

At the time, [`core-model.md`](../../spec/core-model.md) §2.5 permitted a
requester to request *"a subset or a coarser form"* of the registered domain.
**Subset and coarser are not equally safe, and the specification treated them as
one allowance.**

**Coarsening** maps every registered value onto a smaller set — exact time to a
two-hour band, fifteen values to three. Every possible result has an image. No
result falls outside the domain.

**Subsetting** selects some registered values and discards the rest. A result
among the discarded values falls outside the requested domain, and
[`core-model.md`](../../spec/core-model.md) §3 requires failing closed.

That failure is informative:

> A requester asks `menu_compatible` with a requested domain of `[true]`.
> A `true` result returns `true`, and debits `ceil(1000 × log2(1)) = 0` millibits.
> A `false` result falls outside the domain and returns a denial.
>
> Either way the requester learns the answer. **The debit is zero.** Denial
> normalization does not help — the requester constructed a question whose only
> failure mode is the answer it wanted, and no uniformity of response can erase
> what it already knows about its own request.

This defeats Q2D-C-09 for any predicate whose domain can be subsetted, and it
does so without violating any current requirement.

**Two candidate resolutions.**

**(A) Reject strict subsets; permit coarsening only.** The narrowing check
requires every registered value to have an image in the requested domain.
Simplest, closes the leak completely, and costs little — every worked example of
narrowing in the technical report is a coarsening, and every current registry
entry is unaffected.

**(B) Charge the subset as cardinality *k*+1 and debit the out-of-domain
denial.** A subset of size *k* has *k*+1 outcomes: each value, or "outside".
Honest accounting, and it is exactly the shape `availability_window` already uses
— its `null` is the "none of the above" outcome and is counted. But it forces
[`core-model.md`](../../spec/core-model.md) §9's open item on whether denials
debit the budget, and an uncharged denial reopens the same hole.

**Resolved: (A).** Escalated and decided. Amended:
[`core-model.md`](../../spec/core-model.md) §2.5 now permits coarsening and
prohibits subsetting, and extends the same rule to policy modifiers so every
result retains an image throughout the intersection;
[`terminology.md`](../../spec/terminology.md) §6 matches on both the effective
answer domain and decision modifier entries; and
[`claims.md`](../../spec/claims.md) Q2D-C-09 now records that it holds only
because subsetting is prohibited.

(B) is recorded as the shape a later profile would take, and remains coupled to
[`core-model.md`](../../spec/core-model.md) §9's open item on whether denials
debit.

### 4.5 What "no broader" means per shape

Assuming resolution (A). Each rule is a total function from registered domain and
requested domain to admissible or reject.

| Shape | Narrowing permitted |
|---|---|
| `boolean` | none — must equal the registered domain |
| `enum` | coarsening only: a total mapping onto a smaller value set |
| `scalar` | reduced precision; a range no wider than registered |
| `interval` | coarser granularity, at or above any `minimum_slot_duration`; horizon no longer than registered |
| `set` | `maximum_cardinality` at or below registered |
| `object` | `allowed_detail_fields` a subset of registered; each field narrowed by its own shape's rule |
| `attribute` | none |
| `ciphertext` | not reachable in MVP |

`object` is the one to watch: it recurses, and a field-level rule must not be
skipped because the object-level check passed.

### 4.6 Assurance profile

The request's requested profile must appear in the entry's
`assurance_profiles`. A profile the responder does not support is a rejection,
never a downgrade — the same rule as suite selection in
[P-003](P-003-crypto-suites.md), and for the same reason.

## 5. Interfaces

```
validate_schema(public_context, entry) -> Result           // profile-restricted
check_constraints(public_context, entry) -> Result         // closed vocabulary
check_narrowing(requested: Domain, entry) -> Result<Domain> // admissible domain
apply_modifiers(admissible: Domain, mods: [Modifier]) -> Result<Domain> // effective
supports_profile(requested: ProfileId, entry) -> bool
```

`check_narrowing` returns the admissible domain rather than a boolean, so a
caller cannot check narrowing and then proceed with the requester's domain — the
validated value is the only one it gets.

## 6. Corpus sections

`domain/` — authored under this PRD.

| Group | Vectors |
|---|---|
| `domain/schema/` | Valid context; each profile keyword; a schema using a forbidden keyword rejects |
| `domain/constraints/` | Slot below floor; horizon beyond limit; both boundaries exact |
| `domain/narrowing/` | Per shape in §4.5: valid coarsening, attempted expansion, and attempted strict subset — the last two both reject |
| `domain/intersection/` | Admissible from registry ∩ requested; effective from admissible ∩ modifiers; empty at either phase |
| `domain/profile/` | Supported profile passes; unsupported rejects without downgrade |

## 7. Acceptance

- [ ] Both implementations compute identical admissible and effective domains for
      every `domain/intersection/` vector.
- [ ] A schema using a keyword outside the §4.2 profile is rejected **as a
      registry error**, distinctly from a request that fails validation against a
      valid schema.
- [ ] Every current entry in `registry/manifest.json` validates under the profile.
- [ ] An expansion attempt rejects for every shape in §4.5.
- [ ] `object` narrowing recurses — a valid object-level narrowing with an invalid
      field-level one rejects.
- [ ] An unsupported assurance profile rejects and the response names no
      alternative.

## 8. Negative acceptance

| Must fail | Observed as |
|---|---|
| Any domain expansion | Rejected for every shape |
| A requester-supplied domain reaching the effective domain unvalidated | `check_narrowing` returns the domain; no caller can bypass it |
| Modifiers applied before the narrowing check | Ordering vector shows a policy modifier widening an inadmissible request into an admissible one |
| `object` field-level narrowing skipped | Nested invalid narrowing accepted |
| Two implementations disagreeing on a schema edge case | `domain/schema/` cross-implementation comparison fails |
| A constraint outside the closed vocabulary silently ignored | Unknown constraint key in an entry is a registry error, not a no-op |
| An unsupported profile silently downgraded | Response carries a profile the request did not ask for |

Row 3 is the one the three-domain vocabulary in §4.1 exists to prevent, and it is
worth a dedicated ordering vector: a modifier must never be able to rescue a
request the contract check rejected.

Row 6 matters more than it looks. An unknown constraint key silently ignored
means a registry can add an anti-probing control that one implementation enforces
and the other does not.

## 9. Escalate-if-changed decisions

1. **The registry may use only the §4.2 JSON Schema profile.** Widening it
   reintroduces cross-implementation disagreement about validity.
2. **The constraint vocabulary is closed**, and an unknown key is an error rather
   than a no-op.
3. **`check_narrowing` returns the admissible domain.** A boolean would let a
   caller proceed with the requester's value.
4. **Modifiers apply after the narrowing check, never before.**
5. **An unsupported assurance profile rejects; it never downgrades.**
6. **§4.4's resolution**, once made, is architecture — it determines what a
   requester is allowed to ask for.

## 10. Open questions

| Question | Belongs to |
|---|---|
| ~~§4.4 — subset narrowing is a free oracle~~ | **Resolved as (A).** Spec amended; see §4.4 |
| Does an empty intersection reject before or after policy? Proposed: before, since an inadmissible request should not consult authorities | This PRD |
| Should the schema profile be stated in `spec/` rather than only here? Proposed: yes — it constrains what a registry may contain, which is protocol surface | This PRD; likely a `scope.md` addition |
| Does a coarsening mapping need to be declared by the requester, or inferred? Proposed: declared, so the responder validates a stated mapping rather than guessing one | This PRD; blocks issue 4 |

## 11. Issues

| # | Issue | Done when |
|---|---|---|
| 1 | ~~Escalate §4.4~~ — **done** | Resolved as (A); `core-model.md` §2.5, `terminology.md` §6, `claims.md` Q2D-C-09 amended |
| 2 | JSON Schema profile validator | Forbidden keywords rejected as registry errors; `domain/schema/` passes |
| 3 | Constraint evaluation, closed vocabulary | `domain/constraints/` passes; unknown key errors |
| 4 | `check_narrowing` per shape | `domain/narrowing/` passes; open question 4 resolved first |
| 5 | `object` recursion in narrowing | Nested invalid narrowing rejects |
| 6 | `apply_modifiers` and the two-phase intersection | `domain/intersection/` passes; ordering vector passes |
| 7 | `supports_profile` | `domain/profile/` passes; no downgrade path exists |
| 8 | Assert every registry entry validates under the profile | CI check over `registry/manifest.json` |
| 9 | Author `domain/` corpus section | Five groups; `harness lint` clean |

Issue 1 is complete. Issue 4 now has a settled rule to implement, and §4.5's
table is the specification of it.
