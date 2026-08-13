# P-007 — Policy engine contract and fail-closed invariants

| Field | Detail |
|---|---|
| PRD | P-007 |
| Stage | 3 |
| Status | **Ready for decomposition** |
| Size | L |
| Risk | medium |
| Depends on | [P-001](P-001-conformance-corpus.md), [P-005](P-005-registry-client.md), [P-006](P-006-request-validation.md) |
| Blocks | P-008, P-009, P-010, P-011, P-015, P-016 |

---

## 1. Purpose

Define the policy engine's input and output contract, the composition rule across
multiple authorities, and the fail-closed invariants no configuration may
override.

Q2D deliberately does not define a policy language. It defines what a policy
engine is *given*, what it must *return*, and what it may never do. XACML,
OPA/Rego, or local code may implement the contract.

**Claims served:** Q2D-C-08 and Q2D-C-09 both depend on this module — a
normalized denial and a budget decision are both outcomes of a policy decision.
Its own contribution is the fail-closed guarantee underneath both.

## 2. Spec citations

| Source | What it constrains here |
|---|---|
| [`spec/core-model.md`](../../spec/core-model.md) §4 step 14 | Policy evaluation and its position — after all validation, before private access |
| [`spec/core-model.md`](../../spec/core-model.md) §3 | Modifiers narrow the admissible domain into the effective domain |
| [`spec/core-model.md`](../../spec/core-model.md) §2.5 | Modifiers coarsen; they never subset |
| [`spec/terminology.md`](../../spec/terminology.md) §6 | Policy engine; decision modifier; the restrictive-composition default |
| [`spec/conformance-classes.md`](../../spec/conformance-classes.md) CC-3 | The class this module implements, and what it must not claim |
| [`spec/claims.md`](../../spec/claims.md) Q2D-C-08, Q2D-C-09 | Both list the policy engine among what must not misbehave |
| [`threat-model/trust-matrix.md`](../../threat-model/trust-matrix.md) §3 | A compromised policy engine defeats C-08 and C-09 and nothing else |

## 3. Module boundary

**Inside:** the decision input contract; the three outcomes and their modifiers;
authority composition; the fail-closed invariants and their property tests;
determinism requirements; separation of the audit reason from the wire outcome.

**Explicitly outside:** a policy language or rule syntax. Budget arithmetic and
storage (**P-008**) — this module *consults* disclosure history and *reads* a
budget verdict, but computes nothing. Mapping a decision to a wire response
(**P-009**). The escalation lifecycle (**P-015**); this module can return
`escalate` but owns none of what happens next. Predicate evaluation
(**P-010**).

## 4. Design

### 4.1 The policy engine cannot see the answer

Policy runs at step 14. Private input is read at step 16. **A policy decision is
therefore made without knowing the answer, and that is a security property rather
than an ordering accident.**

A policy conditioned on the result — *allow if the answer is `false`* — would
convert the allow/deny outcome into a disclosure of the answer, at zero capacity
cost. It is the same shape as the subsetting leak resolved in
[`core-model.md`](../../spec/core-model.md) §2.5, arriving through a different
door.

The contract enforces this structurally: **the decision input contains no field
derived from private data.** There is no parameter a policy could condition on to
learn the result, and adding one is an escalation, not a feature.

A deployment that genuinely needs a data-dependent release rule expresses it as a
*predicate*, where the registry bounds its domain and the budget charges it —
not as policy, where neither applies.

### 4.2 Decision input

```
PolicyInput {
  requester      { principal, agent, delegation_verified }
  custodian
  subjects[]
  predicate      { id, version, sensitivity_class }
  purpose        { code, description, requested_retention, onward_transfer }
  delivery       { answer_recipient, model_endpoint, permitted_sinks[],
                   required_containment_profile }
  admissible_domain
  requested_assurance
  disclosure_history  { relationship, window, spent_millibits, limit_millibits }
  grant          Option<{ scope_digest, granted_at, expires_at }>
  environment    { now, deployment_context }
}
```

Every field is either signature-covered, registry-derived, or local state. None
is derived from private input (§4.1), and none is taken from `routing`.

`grant` reports an **unconsumed, unexpired** grant whose approval-scope digest
matches this request, and nothing else. It is policy state, not private-derived
data, so §4.1's invariant is untouched.

Two properties of the shape carry the weight:

- **It is an input, not a decision.** A grant that short-circuited the pipeline
  would be an answer cached under another name.
  [P-015](P-015-escalation-lifecycle.md) §4.4 has the same shape as
  [P-008](P-008-capacity-accounting.md) §4.6's `Exhausted` verdict — the module
  reports, this one decides. A revoked authority therefore overrides a grant with
  no special case, because §4.4's most-restrictive composition denies regardless
  of what `grant` says.
- **Policy reads it; policy never consumes it.** A grant is **single-use**
  ([`core-model.md`](../../spec/core-model.md) §5.3), and consumption happens on
  release, alongside the budget debit at step 18, inside the same atomic commit
  ([P-004](P-004-replay-idempotency.md) §4.6). Consuming at step 14 would burn a
  human's approval on an exchange that then failed output validation or found the
  budget exhausted — a person's decision spent on nothing released.

`environment.now` is **passed in**, not read. A policy engine that reads a clock
is non-deterministic and therefore not testable against a vector.

### 4.3 Decision output

```
Decision {
  outcome       : allow | deny | escalate
  modifiers     : [Modifier]      // allow only
  on_exhaustion : deny | escalate // applied at step 15; policy does not run again
  audit         : { reason, authorities_consulted, policy_version }
  external      : ExternalClass   // what P-009 may put on the wire
}
```

`on_exhaustion` exists because of an ordering constraint rather than a
preference. [`core-model.md`](../../spec/core-model.md) §4 runs policy once at
step 14 and checks the budget at step 15 — the debit cannot be computed before
step 14's modifiers exist — so a policy engine cannot be asked what to do about
exhaustion *after* exhaustion is discovered. It decides in advance, from the
`disclosure_history` §4.2 already gives it, and step 15 applies the answer.
[P-008](P-008-capacity-accounting.md) §4.6 carries the same reasoning from the
other side.

`audit` and `external` are **separate fields, populated separately**. The
temptation is to derive `external` from `reason` at the end; that is how an
internal reason reaches the wire. Keeping them apart means a leak requires
someone to deliberately copy one into the other.

Modifiers may only coarsen ([`core-model.md`](../../spec/core-model.md) §2.5),
and **not an `enum`** — §3.2, which now gives the reason: an `enum` is the one
shape narrowed by an arbitrary function rather than an ordered parameter, so two
coarsenings of it need not compose. [E-25](../open-escalations.md) decided this
rather than deferring it; it is a settled rule here, not a placeholder. A
modifier producing a strict subset of the admissible domain is rejected by
[P-006](P-006-request-validation.md)'s `apply_modifiers`, and that rejection is
an implementation error rather than a policy outcome — a policy engine that emits
one is broken, not restrictive.

### 4.4 Composition across authorities

Where several authorities apply, the decision is the **most restrictive**:

```
deny  >  escalate  >  allow
```

An `allow` requires **every** mandatory authority to permit. Any mandatory `deny`
prevents. Any `escalate` from an authority that has not denied produces
`escalate`.

Modifiers from all permitting authorities are **unioned**, not merged — every
narrowing applies. Where two authorities narrow the same dimension, what they
compose to is [`core-model.md`](../../spec/core-model.md) **§3.3** (E-26). This
module implements that section and states none of it.

One warning, because this section carried the shortcut until E-26 closed:
*coarser of the two* is not the general rule. Some of the dimensions §3.3 covers
are not ranked by coarseness at all, so an implementation that compares two
operands and returns the coarser is wrong for them, and wrong in a way that
returns an answer rather than an error. Read §3.3 before writing `compose`.

`enum` never reaches here: §3.2 excludes it from modifier coarsening (E-25).

That is the same rule [`core-model.md`](../../spec/core-model.md) §3 states for
the effective domain as a whole: composition of narrowings rather than an
intersection of their *values*. Two-hour bands composed with four-hour bands
yield four-hour bands; as sets of values they would intersect to nothing. Where
§3.3 does intersect, it intersects the narrowing's own parameter — a field set, a
pair of endpoints — for which containment *is* the narrowing order.

An authority that cannot be reached, times out, or returns something
unparseable counts as a **mandatory deny**, not as absent.

### 4.5 The fail-closed invariants

Six invariants, and **no configuration, rule file, or user-authored policy may
override any of them.** They are properties of the engine, not defaults within
it.

| # | Invariant |
|---|---|
| F1 | No matching rule → `deny` |
| F2 | Missing mandatory input field → `deny` |
| F3 | An authority unreachable, timing out, or returning an unparseable result → `deny` |
| F4 | Mandatory authorities disagreeing irreconcilably → `deny` |
| F5 | An unrecognised sensitivity class, purpose code, or assurance profile → `deny` |
| F6 | An internal error at any point → `deny` |

These are tested as **properties over generated inputs**, not as examples. An
example test proves one input denies; a property test proves no input in a class
permits. F1 in particular is the one an example suite always appears to cover and
never does.

### 4.6 Determinism

Same input, same decision, in both implementations.

No clock (§4.2), no RNG, no iteration over an unordered collection where the
order reaches the outcome, no locale-dependent comparison. Rule evaluation order
must be total and defined — where rules are ordered, the order is explicit in the
rule set rather than emergent from a map.

This is what makes `policy_decide` a corpus operation at all. A non-deterministic
engine cannot be cross-checked, and a policy engine that cannot be cross-checked
is a policy engine whose two implementations differ in what they permit.

### 4.7 What CC-3 may not claim

[`conformance-classes.md`](../../spec/conformance-classes.md) CC-3 is explicit
that this class must not disclose policy reasoning in an externally visible
response unless a policy explicitly permits it. This module's contribution is
§4.3's separation; the enforcement is [P-009](P-009-denial-normalization.md)'s.

Neither module alone is sufficient, and the corpus tests the seam rather than
either side.

## 5. Interfaces

```
decide(input: PolicyInput, rules: RuleSet) -> Decision
compose(decisions: [Decision]) -> Decision          // most-restrictive
validate_rules(rules: RuleSet) -> Result            // load-time
```

`validate_rules` runs at load and rejects a rule set that attempts to override an
F-invariant, references an unknown sensitivity class or purpose code, or is
ambiguous in evaluation order. **A rule set that would violate an invariant fails
at load, not at decision time** — a responder should refuse to start rather than
discover the problem on a live request.

## 6. Corpus sections

`policy/` — authored under this PRD.

| Group | Vectors |
|---|---|
| `policy/outcome/` | Each of the three outcomes from an explicit rule |
| `policy/compose/` | Every pair and triple over `{allow, deny, escalate}`; modifier union; two authorities narrowing one dimension, in each of the three cases [`core-model.md`](../../spec/core-model.md) §3.3 distinguishes — comparable, incomparable, and disjoint |
| `policy/failclosed/` | F1–F6, each as a property over generated inputs |
| `policy/modifiers/` | Valid coarsening; an attempted subset is an implementation error; **an attempted `enum` coarsening likewise**, per [`core-model.md`](../../spec/core-model.md) §3.2 — settled by E-25, so a vector asserting it is asserting a rule rather than a temporary position |
| `policy/determinism/` | Same input twice; permuted authority order; permuted rule-set map order |
| `policy/separation/` | An audit reason never appears in `external` |
| `policy/rules/` | A rule set overriding an invariant fails at load |
| `policy/grant/` | A matching grant is an input, not an outcome: a revoked authority still denies, an expired grant does not appear, and an already-consumed one does not appear |

## 7. Acceptance

- [ ] Both implementations return identical decisions for every `policy/` vector,
      including identical modifier sets.
- [ ] F1–F6 hold as **property tests** over generated inputs in both
      implementations, not as example tests.
- [ ] Composition is order-independent — permuting authorities does not change
      the outcome.
- [ ] A rule set attempting to override any F-invariant is rejected at load.
- [ ] `PolicyInput` contains no field derived from private input, asserted by
      reviewing the type rather than by test.
- [ ] `environment.now` is a parameter; no clock read exists in the module,
      asserted by dependency check.

## 8. Negative acceptance

| Must fail | Observed as |
|---|---|
| A policy conditioning on the answer | No such field exists in `PolicyInput`; the type does not permit it |
| A configuration overriding F1–F6 | Rejected at load, not at decision time |
| An unreachable authority treated as absent | Composition returns `allow` where it must return `deny` |
| A modifier producing a strict subset | `apply_modifiers` errors; the decision is an implementation error, not a restriction |
| A clock read inside the engine | Dependency check finds a time source |
| Authority order changing the outcome | `policy/determinism/` permutation vector fails |
| An audit reason reaching `external` | `policy/separation/` fails |
| An engine returning `allow` with an empty modifier set where an authority required one | Modifier union drops a narrowing |

Row 1 is the important one, and it is enforced by a type rather than a test —
there is no way to write the offending policy because the input does not carry
the value it would need.

## 9. Escalate-if-changed decisions

1. **`PolicyInput` carries nothing derived from private input.** Adding such a
   field converts allow/deny into an answer oracle at zero capacity cost.
2. **`audit.reason` and `external` are separate fields, populated separately.**
3. **Composition is most-restrictive, and an unreachable authority is a deny.**
4. **F1–F6 are properties of the engine, not overridable defaults.**
5. **Rule sets are validated at load; an invariant violation refuses to start.**
6. **`environment.now` is passed in.** A clock read makes the engine untestable.
7. **Modifiers coarsen only** — inherited from
   [`core-model.md`](../../spec/core-model.md) §2.5 rather than decided here.

## 10. Open questions

| Question | Belongs to |
|---|---|
| ~~Which authorities are *mandatory* versus advisory, and who declares that?~~ | **Resolved: custodian configuration, fixed at load.** It cannot come from the request — a requester that could mark an authority advisory would have demoted the authority that was about to deny it. Fixed at load rather than per-request means the composition in §4.4 is a property of the deployment and is reproducible against a vector. An authority that fails to load is a **startup failure**, not a silently advisory one |
| ~~Does `escalate` consult the budget before or after?~~ | **Answered: neither — it cannot.** Policy runs once at step 14, the budget is checked at step 15, so the disposition is decided in advance as `on_exhaustion` (§4.3). [P-008](P-008-capacity-accounting.md) §4.6 |
| ~~Is a rule language shipped at all in MVP, or is the engine a code interface with a fixture rule set?~~ | **Resolved: a code interface with a fixture rule set.** [`scope.md`](../../spec/scope.md) and CC-3 both say Q2D specifies the policy input and output contract and not a language, so shipping one would make the reference implementation's language read as part of the protocol. The fixture set exists to exercise §4.4 composition and the §4.5 invariants, and is explicitly not a starting point for a deployment's rules |
| ~~How are modifiers from two authorities coarsening the same dimension combined — coarser wins, or intersect?~~ | **Answered: it depends on the dimension** — this row said *coarser wins*, which was right for the dimensions considered at the time and wrong for those ordered by containment. Superseded by E-26, the row below; [`core-model.md`](../../spec/core-model.md) §3.3 is where the answer lives |
| ~~**`PolicyInput` needs a grant field.**~~ | **Resolved and applied.** Grants are single-use ([`core-model.md`](../../spec/core-model.md) §5.3), so the field reports an *unconsumed* match and consumption happens at release rather than at step 14. §4.2 amended |
| ~~Should a modifier be able to coarsen an `enum`, by carrying a mapping of its own?~~ | **Resolved: no** ([`open-escalations.md`](../open-escalations.md) E-25). The cost is not the field but the composition rule it would require. Two `enum` mappings need not be comparable, and their common coarsening is strictly coarser than each, so its label set is one neither party declared and §3.2's second condition rejects it. The other shapes have an answer, in §3.3 — E-26, below. No field is added to `Decision`; issue 8 rejects the attempt |
| ~~What do two modifiers emitting incomparable narrowings of one dimension compose to?~~ | **Resolved** ([`open-escalations.md`](../open-escalations.md) E-26): [`core-model.md`](../../spec/core-model.md) **§3.3** is new and answers it per dimension. Worth knowing when decomposing issue 4 — the escalation named three incomparable shapes and one of them, `interval` granularity, was not: it is a duration, and durations are ranked |

## 11. Issues

| # | Issue | Done when |
|---|---|---|
| 1 | `PolicyInput` and `Decision` types, both languages | No private-derived field; `audit` and `external` separate |
| 2 | `decide` over a fixture rule set | `policy/outcome/` passes |
| 3 | F1–F6 as property tests | `policy/failclosed/` passes; generators cover each class |
| 4 | `compose` with most-restrictive ordering and modifier union | `policy/compose/` passes, with a comparable, an incomparable and a disjoint operand pair for each dimension §3.3 covers — less disjoint `allowed_detail_fields`, which waits on E-27 with [P-006](P-006-request-validation.md) issue 4. Each result is the one [`core-model.md`](../../spec/core-model.md) §3.3 gives, which is not the same outcome for every dimension |
| 4a | `grant` field on `PolicyInput`, read-only | `policy/grant/` passes; no code path in this module consumes a grant |
| 5 | `validate_rules` at load | `policy/rules/` passes; invariant override refuses to start |
| 6 | Determinism: explicit rule ordering, no clock, no map iteration | `policy/determinism/` passes; dependency check clean |
| 7 | Audit/external separation | `policy/separation/` passes |
| 8 | Modifier emission constrained to coarsening, and to shapes other than `enum` | Subset attempt errors as an implementation fault; so does an `enum` narrowing, per [`core-model.md`](../../spec/core-model.md) §3.2 |
| 9 | Author `policy/` corpus section | Seven groups; `harness lint` clean |
| 10 | Resolve open questions 1 and 3 | Written into §4.4 and §5 before issues 4 and 5 |

Issue 1 blocks everything. Issue 3 is the largest — property generators for six
invariant classes in two languages is most of this PRD's weight.

Issue 4a is small but easy to get wrong in a way nothing catches: the grant must
be read here and consumed at release ([P-015](P-015-escalation-lifecycle.md)
§4.4). A module that consumes what it reads spends a human's approval on an
exchange that may still fail.
