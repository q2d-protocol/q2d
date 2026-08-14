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

**Inside:** public-context schema validation; enforcing
[`scope.md`](../../spec/scope.md) §4.1's JSON Schema profile — the rule is
`spec/`'s, the enforcement is this module's; per-predicate constraint checks; contract narrowing validation;
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

**`narrow` does not intersect domains.** Two coarsenings of different
granularity — two-hour bands against four-hour bands — compose to the coarser,
where an intersection of their literal values would be empty. It is not the case
that nothing is ever intersected: [`core-model.md`](../../spec/core-model.md)
§3.3 draws the line between intersecting a domain and intersecting a narrowing's
own parameter, and an implementation that treats "not an intersection" as a
general rule gets two dimensions wrong. The per-shape rules are normative in
§3.2 and §3.3; §4.5 below is how this module implements them and adds
nothing. An implementation that reads §3's
expression as a set operation denies requests it should serve and, where it does
not deny, charges the wrong debit.

A domain that is genuinely unsatisfiable at either phase fails closed.

### 4.2 The JSON Schema profile

Two JSON Schema libraries can disagree on edge cases, and a disagreement here is
a cross-implementation divergence in what counts as a valid request.

**The profile is [`scope.md`](../../spec/scope.md) §4.1's**, and this module
enforces it: a registry schema using anything outside that subset is rejected.
The list is there rather than here, and this section cites it rather than
restating it.

It was here, and E-16 moved it. The reason is worth keeping: a rejection rule
about *registry content* stated only in a PRD means a third implementation built
from `spec/` alone accepts manifests this PRD specifies ours to reject —
neither wrong by the document it was built from, which is the divergence the
context hierarchy exists to prevent, with the rule one level too low.

Moving it surfaced **two keywords the list had missed**, both used by every
relevant entry in [`registry/manifest.json`](../../registry/manifest.json):
`$schema`, and `items` for array element schemas. The claim here that every
entry already fitted the profile was therefore not true of the list as written.
§4.1 carries both — `$schema` required, because two implementations validating
against different dialects is the same divergence one level up — and
`registry/validate.py` now enforces the profile over the manifest rather than
leaving it to the implementations — across all three of an entry's schemas, and
`additionalProperties: false` on every object rather than only the root.

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
  implement wrongly, because the outer check looks complete. Its
  `allowed_detail_fields` is also **non-empty** — an object with no fields is the
  constant release E-27 refused.
- **`enum` coarsens by a mapping the requester declares**, in
  `answer_contract.coarsening`, which this module validates against §3.2's five
  conditions: total, image exactly equal to the requested domain, non-expanding,
  a function, and at least two labels. All five are set
  comparisons and counts — **this module makes no judgement about what a label
  means**. A mapping a human would call wrong is admissible; Q2D-C-01 binds the
  requester to the commitment it made, and what a responder guarantees is that
  the answer lies inside the requested domain, not that the question was
  sensible.

  Capacity comes from the label count, looked up in the entry's capacity table
  as any varying cardinality is. A count the table does not cover is a registry
  defect and a `blocker`, per [P-008](P-008-capacity-accounting.md) §4.

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
| `domain/narrowing/` | Per shape in §4.5: valid coarsening, attempted expansion, and attempted strict subset — the last two both reject. For `enum`, one vector per §3.2 condition: a mapping that is not total, whose image omits a requested label, whose image carries a label outside the requested domain, that is not non-expanding, that is not a function, and **that maps every registered value onto one label** (E-27). For `object`, an empty `allowed_detail_fields` |
| `domain/compose/` | Admissible from `narrow(registry, requested)`; effective from `narrow(admissible, modifiers)`; two coarsenings of different granularity compose to the coarser rather than to nothing; and one vector for each case [`core-model.md`](../../spec/core-model.md) §3.3 distinguishes — comparable, incomparable, disjoint — per dimension it covers. An unsatisfiable domain at either phase fails closed |
| `domain/profile/` | Supported profile passes; unsupported rejects without downgrade |

## 7. Acceptance

- [ ] Both implementations compute identical admissible and effective domains for
      every `domain/narrowing/` and `domain/compose/` vector.
- [ ] Composing two coarsenings of different granularity yields the coarser, and
      **not** an empty domain — the failure a set-intersection reading produces.
- [ ] A schema outside [`scope.md`](../../spec/scope.md) §4.1's profile — a
      keyword it does not list, a nested `$schema`, a boolean subschema, or an
      object without `additionalProperties: false` — is rejected **as a
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
| **Composition implemented as intersection of domain values** | `domain/compose/` denies a request whose requested and modifier granularities differ — the reading [`core-model.md`](../../spec/core-model.md) §3 was amended to rule out |
| **Composition implemented as "first modifier wins", or by ranking operands that §3.3 does not rank** | `domain/compose/` returns a value one operand permitted and another did not |

Row 3 is the one the three-domain vocabulary in §4.1 exists to prevent, and it is
worth a dedicated ordering vector: a modifier must never be able to rescue a
request the contract check rejected.

Row 6 matters more than it looks. An unknown constraint key silently ignored
means a registry can add an anti-probing control that one implementation enforces
and the other does not.

## 9. Escalate-if-changed decisions

1. **The registry may use only [`scope.md`](../../spec/scope.md) §4.1's JSON
   Schema profile.** Widening it reintroduces cross-implementation disagreement
   about validity — and widening it is now a `spec/` change, not this module's
   to make, which is what E-16 moved and why.
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
| ~~Should the schema profile be stated in `spec/` rather than only here?~~ | **Resolved: yes** — [`scope.md`](../../spec/scope.md) §4.1 ([`open-escalations.md`](../open-escalations.md) E-16). §4.2 cites it and this module enforces it; widening the list is now a `spec/` change rather than this module's to make. Moving it found `$schema` missing from the list while present in every entry |
| ~~Does a coarsening mapping need to be declared by the requester, or inferred?~~ | **Resolved: declared** ([`open-escalations.md`](../open-escalations.md) E-17). `answer_contract.coarsening` carries it, and this module validates it against [`core-model.md`](../../spec/core-model.md) §3.2's conditions — total, image exactly equal to the requested domain, non-expanding, a function, and at least two labels, the last added by E-27. All are set comparisons and counts; §4.5 records that no judgement about a label's *meaning* is made here |
| ~~And may a *policy modifier* coarsen an `enum`, given it has no answer contract to declare a mapping in?~~ | **Resolved: no** ([`open-escalations.md`](../open-escalations.md) E-25). [`core-model.md`](../../spec/core-model.md) §3.2 states it as a rule with its reason — an `enum` is the one shape narrowed by an arbitrary function, so two coarsenings of it need not compose — rather than as a position held pending a decision. `apply_modifiers` (issue 6) rejects one as an implementation error |
| ~~Is a release that cannot vary with the data admissible?~~ | **Resolved: no** ([`open-escalations.md`](../open-escalations.md) E-27). [`core-model.md`](../../spec/core-model.md) §3.2 gains a **fifth** `enum` condition — at least two labels — and requires an `object` release to name at least one detail field. Issue 4 is unblocked for both. The escalation was briefed as a conflict with §2.5's *may be empty*; it is not, because only `object` has detail fields |

## 11. Issues

| # | Issue | Done when |
|---|---|---|
| 1 | ~~Escalate §4.4~~ — **done** | Resolved as (A); `core-model.md` §2.5, `terminology.md` §6, `claims.md` Q2D-C-09 amended |
| 2 | JSON Schema profile validator, per [`scope.md`](../../spec/scope.md) §4.1 | Forbidden keywords rejected as registry errors; a missing `$schema` likewise; `domain/schema/` passes. **§4.1 is not only a keyword list** — it also carries rules about how the profile is used and one about a *value*: an `integer` in any of an entry's schemas states `minimum` and `maximum`, both within −2^63 … 2^63 − 1 ([E-37](../open-escalations.md)). A validator that checked only which keywords appear would pass an entry admitting an integer neither implementation can represent |
| 3 | Constraint evaluation, closed vocabulary | `domain/constraints/` passes; unknown key errors |
| 4 | `check_narrowing` per shape, implementing [`core-model.md`](../../spec/core-model.md) §3.2 | `domain/narrowing/` passes for every shape, including a contract carrying `maximum_cardinality`, which [`core-model.md`](../../spec/core-model.md) §2.5 admits for `set` only (E-29) — a contract carrying it for any other shape is rejected. For `enum`, a declared mapping is admitted when it satisfies all **five** of [`core-model.md`](../../spec/core-model.md) §3.2's conditions and rejected when it fails any — one negative vector each, the fifth being a mapping onto a single label (E-27). For `object`, an empty `allowed_detail_fields` is rejected, and so is a composition that reaches one. The interim rule this row used to carry — reject any `enum` domain not equal to the registered one — is superseded by E-17 |
| 5 | `object` recursion in narrowing | Nested invalid narrowing rejects |
| 6 | `apply_modifiers` and the two-phase narrowing composition | `domain/compose/` passes; ordering vector passes; every case [`core-model.md`](../../spec/core-model.md) §3.3 distinguishes has a vector and produces what §3.3 gives |
| 7 | `supports_profile` | `domain/profile/` passes; no downgrade path exists |
| 8 | Assert every registry entry validates under the profile | CI check over `registry/manifest.json` |
| 9 | Author `domain/` corpus section | Five groups; `harness lint` clean |

Issue 1 is complete. Issue 4 carries the rules for every shape,
`enum` included: [`core-model.md`](../../spec/core-model.md) §3.2 says a
coarsening mapping is **declared** by the requester and validated here. **E-17**
decided that, replacing the interim rule this section used to carry — reject any
requested domain not equal to the registered one — which was conforming meanwhile
precisely so that no implementation settled the question by accident.

Its `enum` half was blocked on **E-27**, which is now decided: §3.2 carries a
**fifth** condition, *at least two labels*, and an `object` release names at
least one detail field. `check_narrowing` implements five conditions and rejects
a mapping failing any.

**The rule that decided when to block is worth keeping**, because it took several
passes to state. **A PRD blocks when an implementation cannot proceed without
making the decision, not when the spec might change.** An open escalation is not
by itself a reason to stop: it may touch several sections, and freezing
everything it might reach would stall work the spec defines perfectly well. The
test is whether someone could write the code and be following the spec. Two rules
that disagree fail it, and so does no rule at all.

`enum` was that case. §3.2's four conditions admitted a one-label mapping while
[`registry/validate.py`](../../registry/validate.py) authored no debit for one,
so whoever wrote `check_narrowing` had to pick a side — and picking was the
decision.

**`maximum_cardinality` was the last thing blocked here**, and **E-29** settled
it: the field is for `set` only, and measures the domain's size rather than a
count of results. §2.5 says both, so `check_narrowing` rejects a contract
carrying it for any other shape. Nothing in issue 4 waits now.
