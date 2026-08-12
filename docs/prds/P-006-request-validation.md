# P-006 — Request validation and effective answer domain

| Field | Detail |
|---|---|
| PRD | P-006 |
| Stage | 2 — closes it |
| Status | **Ready for decomposition** |
| Size | M |
| Risk | medium |
| Depends on | [P-001](P-001-conformance-corpus.md), [P-002](P-002-message-envelope.md), [P-005](P-005-registry-client.md) |
| Blocks | P-007, P-008, P-010, P-012, P-016 |

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
| [`spec/core-model.md`](../../spec/core-model.md) §3 | `effective_domain` as **narrowing composition**, not set intersection; an unsatisfiable domain fails closed |
| [`spec/core-model.md`](../../spec/core-model.md) §3.2 | The per-shape narrowing rules this module implements — normative there, not here |
| [`spec/core-model.md`](../../spec/core-model.md) §2.5 | The answer contract; **coarsening only** — never an expansion and never a strict subset |
| [`spec/core-model.md`](../../spec/core-model.md) §4 steps 11, 11a, 12–13 | Schema validation, the entry's other constraints, contract narrowing, assurance profile support |
| [`spec/claims.md`](../../spec/claims.md) Q2D-C-02 | The domain is resolved by the responder, never accepted from the requester |
| [`spec/terminology.md`](../../spec/terminology.md) §4 | The eight release shapes |
| [`spec/terminology.md`](../../spec/terminology.md) §6 | Effective answer domain; decision modifiers |
| [`registry/manifest.json`](../../registry/manifest.json) | `public_context_schema`, `answer_domain`, `constraints` |

## 3. Module boundary

**Inside:** public-context schema validation; the JSON Schema profile the
registry may use; per-predicate constraint checks; contract narrowing validation;
**implementing** the per-shape narrowing composition
[`core-model.md`](../../spec/core-model.md) §3.2 defines; assurance-profile
support check.

**Explicitly not inside:** defining those rules. §3.2 is normative and this
module conforms to it.

**Explicitly outside:** obtaining the entry (**P-005**). Capacity arithmetic
(**P-008**) — this module produces the domain, P-008 looks up its charge. The
policy decision itself (**P-007**); this module applies modifiers that P-007
returns but never produces one. Output validation against the domain
(**P-010**).

## 4. Design

### 4.1 Three domains, not one

[`core-model.md`](../../spec/core-model.md) §3 states the composition as one
expression, but §4 evaluates it in two phases either side of the policy call.
Naming the intermediate state prevents the bug where modifiers are forgotten or
applied before the contract is checked.

| Term | Is | Computed at |
|---|---|---|
| **Requested domain** | What the contract asks for | supplied by requester |
| **Admissible domain** | `narrow(registry, requested)` | step 12, before policy |
| **Effective domain** | `narrow(admissible, modifiers)` | after step 14 |

*Admissible domain* is implementation vocabulary. It is not a wire concept, does
not appear in a receipt, and must not leak into protocol documentation — only
**effective domain** is a Q2D term.

**`narrow` is not set intersection.** Two coarsenings of different granularity —
two-hour bands against four-hour bands — compose to the coarser, where an
intersection of their literal values would be empty. The per-shape rules are
normative in [`core-model.md`](../../spec/core-model.md) §3.2; §4.5 below is how
this module implements them and adds nothing. An implementation that reads §3's
expression as a set operation denies requests it should serve and, where it does
not deny, charges the wrong debit.

A domain that is genuinely unsatisfiable at either phase fails closed.

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

**This profile is currently defined here and nowhere in `spec/`, which is a
problem this PRD cannot fix.** It is a rejection rule about *registry content*, so
a third implementation built from `spec/` alone would accept manifests both
reference implementations reject — the divergence the context hierarchy exists to
prevent, with the rule one level too low. [`open-escalations.md`](../open-escalations.md)
**E-16** carries it.

It does not block issue 2. The keyword list is settled and every entry in
[`registry/manifest.json`](../../registry/manifest.json) already satisfies it;
E-16 decides **where the rule lives**, not what it says, so resolving it moves
this section's content into `spec/` and leaves §4.2 citing it. What must not
happen meanwhile is any artifact describing the profile as a Q2D requirement —
until E-16 resolves it is a property of these two implementations.

### 4.3 Constraints are separate from schemas

A registry entry's `constraints` object carries checks JSON Schema cannot
express — `minimum_slot_duration` and `maximum_horizon` on
`availability_window` are the current two. They are anti-probing controls, not
usability limits, and are evaluated after schema validation and before private
access.

That ordering is now **[`core-model.md`](../../spec/core-model.md) §4 step
11a**, immediately after step 11's schema validation. This section and §5's two
functions — `validate_schema` and `check_constraints` — had the distinction
before §4 did: the specification had one step where this module always had two
mechanisms, so a rejection from the second could not say where it happened.
A `domain/constraints/` vector states `11a`.

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
result retains an image throughout the narrowing composition;
[`terminology.md`](../../spec/terminology.md) §6 matches on both the effective
answer domain and decision modifier entries; and
[`claims.md`](../../spec/claims.md) Q2D-C-09 now records that it holds only
because subsetting is prohibited.

(B) is recorded as the shape a later profile would take, and remains coupled to
[`core-model.md`](../../spec/core-model.md) §9's open item on whether denials
debit.

### 4.5 What "no broader" means per shape

**The rules are normative and live in
[`core-model.md`](../../spec/core-model.md) §3.2.** They were moved there because
they are protocol surface: an implementer building from `spec/` alone must be able
to compute the same admissible domain this module does, and a rule that governs
two implementations cannot live in one of their PRDs.

This module implements §3.2 and adds nothing to it. Two implementation notes that
are not requirements:

- **`object` recurses**, and the field-level rule must not be skipped because the
  object-level check passed. This is where the per-shape table is easiest to
  implement wrongly, because the outer check looks complete.
- **`enum` rejects any requested domain not equal to the registered one**, per
  §3.2's interim rule, until [`open-escalations.md`](../open-escalations.md)
  **E-17** decides whether a coarsening mapping is declared or inferred. The
  conservative rule is implementable now and is not a placeholder to be relaxed
  locally: relaxing it is what E-17 decides.

Each rule is a total function from registered domain and requested domain to
admissible or reject, so a shape with no rule is a compile error rather than a
silent pass.

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
| `domain/compose/` | Admissible from `narrow(registry, requested)`; effective from `narrow(admissible, modifiers)`; two coarsenings of different granularity compose to the coarser rather than to nothing; an unsatisfiable domain at either phase fails closed |
| `domain/profile/` | Supported profile passes; unsupported rejects without downgrade |

## 7. Acceptance

- [ ] Both implementations compute identical admissible and effective domains for
      every `domain/narrowing/` and `domain/compose/` vector.
- [ ] Composing two coarsenings of different granularity yields the coarser, and
      **not** an empty domain — the failure a set-intersection reading produces.
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
| **Composition implemented as set intersection** | `domain/compose/` denies a request whose requested and modifier granularities differ — the reading [`core-model.md`](../../spec/core-model.md) §3 was amended to rule out |

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
| ~~Does an unsatisfiable domain reject before or after policy?~~ | **Resolved: before**, at step 12. An inadmissible request must not consult policy authorities: doing so would send the purpose, recipient, and sink set of a request that was never admissible to every configured authority, some of which are people. It also keeps the two phases in §4.1 honest — the admissible domain is computed and checked before policy runs, so a modifier can never rescue a contract the registry already rejected |
| Should the schema profile be stated in `spec/` rather than only here? Proposed: yes — it constrains what a registry may contain, which is protocol surface | **Escalation** — [`open-escalations.md`](../open-escalations.md) **E-16**. A `spec/` addition that carries meaning: it would make a manifest using an unlisted keyword non-conforming. **Does not block** — see §4.2 for what may be built meanwhile |
| Does a coarsening mapping need to be declared by the requester, or inferred? Proposed: declared, so the responder validates a stated mapping rather than guessing one | **Escalation** — [`open-escalations.md`](../open-escalations.md) **E-17**. Declaring it adds a field to the answer contract, which is a [`core-model.md`](../../spec/core-model.md) §2.5 change. **Does not block**: §3.2 states a conservative `enum` rule that is conforming today, and E-17 decides whether to widen it |

## 11. Issues

| # | Issue | Done when |
|---|---|---|
| 1 | ~~Escalate §4.4~~ — **done** | Resolved as (A); `core-model.md` §2.5, `terminology.md` §6, `claims.md` Q2D-C-09 amended |
| 2 | JSON Schema profile validator | Forbidden keywords rejected as registry errors; `domain/schema/` passes |
| 3 | Constraint evaluation, closed vocabulary | `domain/constraints/` passes; unknown key errors |
| 4 | `check_narrowing` per shape, implementing [`core-model.md`](../../spec/core-model.md) §3.2 | `domain/narrowing/` passes for every shape, `enum` included under §3.2's conservative rule — a requested `enum` domain not equal to the registered one rejects. **Not blocked by E-17**, which decides whether to widen that rule later |
| 5 | `object` recursion in narrowing | Nested invalid narrowing rejects |
| 6 | `apply_modifiers` and the two-phase narrowing composition | `domain/compose/` passes; ordering vector passes; two coarsenings compose to the coarser |
| 7 | `supports_profile` | `domain/profile/` passes; no downgrade path exists |
| 8 | Assert every registry entry validates under the profile | CI check over `registry/manifest.json` |
| 9 | Author `domain/` corpus section | Five groups; `harness lint` clean |

Issue 1 is complete. Issue 4 is implementable for every shape:
[`core-model.md`](../../spec/core-model.md) §3.2 now carries the rules, including
a conservative `enum` rule — reject any requested domain not equal to the
registered one — that holds until **E-17** decides whether a coarsening mapping
is declared or inferred. E-17 therefore widens what `enum` permits later; it does
not block building the check now.
