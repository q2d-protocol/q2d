# Q2D Core Model — version 0.1

**Protocol version:** 0.1 (pre-release)
**Document status:** Specification spine — working draft, not yet a normative specification.

The abstract exchange: what a query carries, what a response carries, and the
order in which a responder processes them. Bindings map this onto MCP, A2A, or
direct HTTPS without changing its meaning.

This document defines the **model**. Field names below are the canonical names a
binding should preserve where its transport allows. Signature algorithms and
serialization are not fixed here — they are named by suite in
[`crypto-suites.md`](crypto-suites.md).

Terms: [`terminology.md`](terminology.md). Boundaries: [`scope.md`](scope.md).
Properties: [`claims.md`](claims.md). Suites: [`crypto-suites.md`](crypto-suites.md).

Where this document and the technical report disagree, this document governs.

---

## 1. The exchange

One query, one response. The response is exactly one of three outcomes.

```
requester runtime  ──  query  ──▶  responder
                   ◀── response ──
                                   status ∈ { answer, deny, escalate }
```

There is no partial answer and no negotiation round trip. A requester that
cannot accept the effective contract abandons the task and may submit a
different query.

## 2. Query

### 2.1 Envelope

A message has two parts. Only one of them is authoritative.

```
{
  "signed":  "<opaque: the core object and its signature>",
  "routing": { ... non-authoritative projection ... }
}
```

**`signed`** carries the core object and its signature under a registered suite
([`crypto-suites.md`](crypto-suites.md)). The signature covers the exact bytes
transmitted. There is nothing to canonicalize, and a verifier parses the core
object **only after** verifying those bytes.

**`routing`** is a projection for intermediaries that must dispatch or
capability-match without unwrapping. It is advisory:

- a responder **must not** use `routing` for any decision the signature covers;
- `routing` **must** be a strict subset of what `signed` contains — it may
  never introduce a field;
- if the two disagree on any field, the request is **rejected**, not
  reconciled. Disagreement is a tampering signal;
- an intermediary may read `routing`. It must not modify `signed`.

`routing` is kept minimal, because it travels in the clear. It carries at most
`q2d_version`, `type`, `target.custodian`, `predicate.id`, `predicate.version`,
and `expires_at`. **Purpose, sinks, subjects, the answer contract, and public
context are never projected** — a relay has no need for them, and exposing them
would leak precisely what the protocol exists to bound.

This structure is what makes Q2D-C-05 hold by construction rather than by every
intermediary's JSON library behaving identically. It also matters for
interoperability: canonicalization disagreements across language ecosystems are
a classic source of cross-implementation failure, and Q2D targets two
implementations from the start.

### 2.2 Protocol metadata

| Field | Required | Meaning |
|---|---|---|
| `q2d_version` | yes | Core protocol version. |
| `type` | yes | `query`. |
| `query_id` | yes | Identifies this exchange. |
| `issued_at` | yes | Issue time. |
| `expires_at` | yes | After this, the responder rejects. |
| `nonce` | yes | High-entropy; replay context. |
| `correlation_id` | no | For asynchronous escalation. |

**Every timestamp in Q2D — in the core object, in `routing`, and in a receipt —
is RFC 3339 with an uppercase `T`, an uppercase `Z`, and second precision.**
`2026-01-01T00:00:00Z`, and no other spelling of that instant.

RFC 3339 permits lowercase `t` and `z` and a numeric offset such as `+00:00`.
None of those is permitted here, and the narrowing is not fussiness — it is the
same reason RFC 3339 exists as a narrowing of ISO 8601. Three things in this
document depend on one spelling:

- **§4 step 8 compares `routing` against the verified object exactly**, and
  rejects any difference as tampering. With two spellings of one instant, a
  conforming producer's own message reads as tampered — or a verifier must
  compare *instants* rather than values, which means normalizing a projection
  it has no reason to trust in order to decide whether to trust it.
- **§6 grounds the reduced receipt's length guarantee** in none of its fields
  being variable-length. `+00:00` is six characters where `Z` is one, so
  `decided_at` is the one field that could otherwise vary, and Q2D-C-08's size
  condition rests on it not doing so.
- **Two implementations must produce identical bytes** for the same message
  (`crypto-suites.md` §3). A choice of spelling is a choice they can make
  differently while both believing they conform.

### 2.3 Principals and authority

| Field | Required | Meaning |
|---|---|---|
| `requester.principal` | yes | The accountable party. |
| `requester.agent` | yes | The delegated software acting for it. |
| `requester.delegation` | profile-dependent | Evidence or reference proving the agent acts for the principal. |
| `target.custodian` | yes | The participating custodian addressed. |
| `target.executor` | no | Intended computation executor, where a deployment distinguishes it. |
| `target.subjects` | no | Relevant data subjects, where applicable. |
| `policy_authority_hint` | no | A hint the responder **may ignore**. It never determines which authorities apply. |

Q2D defines three interfaces here rather than one identity technology: principal
identification, key resolution, and delegation verification. Local pairing,
enterprise OIDC/OAuth, and DID/UCAN are profiles over those interfaces.

```
resolve_key(key_id)                              -> PublicKey
identify_principal(key_id)                       -> PrincipalId
verify_delegation(principal, agent, evidence, at) -> ok | fail
```

The signatures are **technology-free**: no key format, no transport, no
enrolment ceremony. A profile supplies those. Two properties of the shape carry
security meaning and are therefore fixed here rather than left to a profile:

- **`identify_principal` is separate from `resolve_key`.** They answer different
  questions — *what key is this?* and *whose is it?* A single lookup returning
  both lets a caller hold a principal it never checked was bound, because the
  operation that produced the key also produced the name.
- **`verify_delegation` returns success or failure, not the evidence.** There is
  nothing a caller should learn from a delegation check beyond that it passed.
  Returning the evidence invites something downstream to read a field out of it
  and treat identity as policy input.

Defining these interfaces does **not** decide which profile, if any, is mandatory
to implement. That remains parked — see §9.

### 2.4 Predicate

| Field | Required | Meaning |
|---|---|---|
| `predicate.id` | yes | Stable identifier. |
| `predicate.version` | yes | Registered version. |
| `predicate.registry_digest` | yes | The digest of the **registry entry** the requester built against. See §2.4.1. |
| `predicate.public_context` | one of | Public input inline. |
| `predicate.public_context_digest` | one of | Or its digest, where the value travels separately. |
| `predicate.requested_assurance` | no | Defaults to `authenticated-answer`. |

A requester selects from registered predicates. Free-form expressions are out of
scope ([`scope.md`](scope.md) §4).

#### 2.4.1 The entry digest, and what a mismatch means

`predicate.registry_digest` is the digest of the **registry entry**, computed
over that entry's canonical bytes with its own digest field removed. It is not
the digest of the manifest.

The two are different objects doing different jobs:

| Digest | Held by | Answers |
|---|---|---|
| Manifest digest | pinned by the custodian | *which registry content has this custodian accepted?* |
| Entry digest | declared by the requester | *do both parties mean the same thing by this predicate?* |

**A mismatch rejects.** Predicate identifiers and versions are meant to be
immutable — a change of meaning requires a new version — but nothing detects a
publisher that mutates an entry in place. Comparing entry digests turns that
convention into a check.

The failure it closes is **semantic mutation without shape change**: a predicate
edited from *"is any item compatible"* to *"does any item conflict"* keeps the
same release shape, domain, capacity, and schema. Every validation passes, the
narrowing is clean, the debit is correct — and the answer means the opposite
of what the requester believes. A manifest-level digest cannot distinguish that
from an unrelated entry being added elsewhere in the same file; an entry-level
digest can.

### 2.5 Answer contract

The requester's pre-evaluation commitment (Q2D-C-01).

| Field | Required | Meaning |
|---|---|---|
| `answer_contract.release_shape` | yes | One of the eight identifiers in [`terminology.md`](terminology.md) §4. |
| `answer_contract.domain` | yes | The requested domain, or a reference to the registry-defined one. |
| `answer_contract.maximum_cardinality` | shape-dependent | For `set` and `object`. |
| `answer_contract.allowed_detail_fields` | yes | May be empty. Never unconstrained — every disclosed field is part of the contract and the capacity calculation. |
| `answer_contract.precision` | shape-dependent | Granularity for `scalar` and `interval`. |
| `answer_contract.coarsening` | shape-dependent | Required for an `enum` request whose domain is coarser than the registered one; prohibited otherwise. The mapping, §3.2. |
| `answer_contract.disclosure_class` | no | Requester's sensitivity assertion; advisory only. |

**A requester may request a coarser form of the registered domain. It may never
expand one, and it may never request a strict subset.** The domain in the query
is a request, not an assertion the responder honours (Q2D-C-02).

*Coarsening* maps every registered value onto a smaller set — exact time to a
two-hour band, fifteen values to three. Every possible result has an image in
the requested domain.

For every shape but `enum` that mapping is implied by the request: a coarser
precision, a wider granularity, a lower cardinality each determine it. For an
`enum` it does not exist until someone supplies it, and **the requester supplies
it** — `answer_contract.coarsening`, validated by the responder under §3.2. It
is not inferred. Inferring would put a semantic judgement about the predicate
into code, and two responders judging differently would return different answers
to one query while both stayed inside the requested domain — a disagreement
invisible from the wire, in the one place where it produces a wrong answer
rather than an error.

*Subsetting* would select some registered values and discard the rest, and is
prohibited because a result among the discarded values would fall outside the
requested domain and fail closed. **That failure is informative.** A requester
asking a boolean predicate with a requested domain of `[true]` receives `true`
for a true result and a denial for a false one, learning the answer either way
while debiting `log2(1)` — nothing. Denial normalization cannot help: the
requester constructed a question whose only failure mode is the answer it
wanted, and no uniformity of response erases what it knows about its own
request. Permitting subsets would defeat Q2D-C-09 for every predicate whose
domain can be subsetted.

The same rule binds policy modifiers (§3, [`terminology.md`](terminology.md) §6):
a modifier coarsens and never subsets, so every result retains an image
throughout the narrowing composition §3 defines.

### 2.6 Purpose and delivery

| Field | Required | Meaning |
|---|---|---|
| `purpose.code` | yes | Machine-readable purpose. |
| `purpose.description` | yes | Human-readable, for the approval interface. |
| `purpose.requested_retention` | no | A request and an obligation, not an enforced control. |
| `purpose.onward_transfer` | no | Likewise. |
| `delivery.answer_recipient` | yes | Who receives the verified answer. |
| `delivery.model_endpoint` | no | **Required if a remote model will receive the answer.** A model provider is a sink. |
| `delivery.permitted_sinks` | yes | May be empty. |
| `delivery.required_containment_profile` | no | e.g. `q2d-contained-runtime-0.1`. |

The protocol separates **declared** purpose from **authorized** purpose. The
query records what the requester claims; the receipt records what the responder
permitted. Neither predicts human behaviour (Q2D-NC-02).

### 2.7 Freshness and authentication

| Field | Required | Meaning |
|---|---|---|
| `freshness.maximum_source_age` | no | Maximum acceptable age of source data or credential evidence. |
| `signature.profile` | yes | The **signature suite** identifier — algorithm, serialization, and hash as one unit. See [`crypto-suites.md`](crypto-suites.md). |
| `signature.key_id` | yes | Resolvable under the identity profile. |
| `signature.value` | yes | Covers every field above. |

`signature.profile` is a field of the **signed** core object, never of the outer
envelope. An intermediary rewriting the envelope therefore cannot change which
suite a verifier believes was used. A verifier applies its own minimum
acceptable policy and rejects suites below it, whatever the sender selected.

Both `signature.profile` and `signature.key_id` are also carried in the
signature's protected header, which §4 step 3 and step 4 read *before* the
payload can be parsed — a verifier cannot choose a policy check or resolve a key
from fields it is not yet allowed to read.
[`crypto-suites.md`](crypto-suites.md) §3 defines that header and why it is
closed. **The fields in this table are the authoritative ones.** The header's copies are
read before anything is authenticated and are therefore untrusted; they exist so
a verifier can reach the point of verifying at all. A verifier confirms each pair
agrees once the signature verifies, and a disagreement rejects.

## 3. Effective answer domain

The responder computes, and never accepts:

```
effective_domain = narrow( registry_entry.canonical_domain,
                           answer_contract.domain,
                           policy_modifiers )
```

The operation is **narrowing composition**, not set intersection. Both the
requester (§2.5) and a policy modifier narrow by *coarsening* — mapping every
registered value onto a smaller set — and two coarsenings of different
granularity are not sets that intersect. Exact times, two-hour bands, and
four-hour bands are three granularities of one domain; composing them yields the
coarsest, not the empty set a literal intersection of their values would give.

Composition is defined per release shape, because what "coarser" means differs
between a scalar, an interval, a set, and an object. The rules are in §3.2. Two
properties hold across every shape:

- **Composition never widens.** Each operand narrows the one before it, so the
  result is no broader than `registry_entry.canonical_domain` (Q2D-C-02).
- **Every possible result retains an image throughout.** This is what §2.5's
  prohibition on subsetting buys, and it is why composition cannot produce an
  empty domain by narrowing alone.

A domain that is nevertheless empty — an unsatisfiable contract, or a modifier
that cannot apply to the requested shape — **fails closed**. The capacity debit
(Q2D-C-09) is computed from the composed value, not from anything the requester
asserted.

### 3.1 Capacity arithmetic

Capacity is carried in **millibits** — thousandths of a bit, as integers.

```
capacity_millibits = ceil(1000 × log2(cardinality))
```

Three rules, and the third is the one that matters:

- **Budgets accumulate by integer addition.** Exact, associative, and
  order-independent. Two conforming responders reach the same total.
- **Rounding is ceiling**, so accounting may over-charge and can never
  under-charge. The error is at most 0.000645 bits per exchange across every
  cardinality the reference registry can produce.
- **A responder reads the value from the registry entry. It never computes
  `log2` at runtime.** IEEE-754 does not require a correctly-rounded `log2`, so
  two implementations could differ in the last place, and a rounding boundary
  would turn that into a different integer. Authoring the value once removes the
  question. Where a domain's cardinality varies with the request, the entry
  carries a lookup table over every reachable cardinality.

This is the same principle as Q2D-C-02 applied to accounting: the registry is
authoritative, and a locally computed value is non-conforming even when it
happens to agree.

Millibits are part of the registry contract. Changing the unit invalidates every
stored budget, so a budget records the unit it was accumulated in.

### 3.2 Narrowing per release shape

Each rule is a total function from a registered domain and a requested domain to
either an admissible domain or a rejection. A responder applies the same rules to
a policy modifier (§2.5).

| Shape | Narrowing permitted |
|---|---|
| `boolean` | none — the requested domain must equal the registered one |
| `enum` | coarsening only, by a mapping the **requester declares** in `answer_contract.coarsening` — see below |
| `scalar` | reduced precision; a range no wider than registered |
| `interval` | coarser granularity, at or above any registered `minimum_slot_duration`; horizon no longer than registered |
| `set` | `maximum_cardinality` at or below registered |
| `object` | `allowed_detail_fields` a subset of registered, each remaining field narrowed by its own shape's rule, applied **recursively** |
| `attribute` | none |
| `ciphertext` | not reachable in 0.1 |

`object` is the one to watch: a field-level rule must not be skipped because the
object-level check passed.

Two shapes deserve their exception stated. `boolean` and `attribute` permit no
narrowing because a two-valued or single-valued domain has no coarser form that
is not the empty request — and a "narrowed" boolean is the subsetting §2.5
prohibits, wearing different words.

**The `enum` mapping is declared, and the responder validates it.** It is
carried in `answer_contract.coarsening` as a map from every registered value to
a requested label, and it is admissible only when all four hold:

1. **Total** — every registered value appears as a key. A missing value is a
   result with no image in the requested domain, which is the subsetting §2.5
   prohibits, arrived at by omission.
2. **Exactly the requested labels** — the mapping's image *equals*
   `answer_contract.domain`, in both directions. No requested label may be
   unreachable: one no registered value maps to is an answer the predicate
   cannot return, and its presence inflates the cardinality the capacity debit
   is computed from. And no other label may be produced: a mapping whose image
   contains a label outside the requested domain can return a result outside
   the domain the requester asked for, which is what Q2D-C-02 and Q2D-C-03
   exist to prevent. Containment in one direction is not enough — a mapping of
   `{a,b,c,d}` onto `{x,y,z}` against a requested domain of `{x,y}` satisfies
   every other condition here and returns `z`.
3. **Non-expanding** — the label set is strictly smaller than the registered
   value set. Equal is not a coarsening and needs no mapping; larger is the
   expansion §2.5 forbids.
4. **A function** — one label per registered value. Two labels for one value is
   not a mapping, and a responder cannot choose between them.

All four are checkable by comparing two sets and counting, which is the point:
the responder makes no judgement about what the labels *mean*. A mapping that
says `via-assistant → not-reachable` is admissible even if a human would call it
wrong, because the requester declared what it wanted and Q2D-C-01 binds it to
that commitment. What the responder guarantees is that the answer it returns is
inside the domain the requester asked for, not that the requester asked a
sensible question.

**A policy modifier may not coarsen an `enum` in 0.1.** The rule above is the
requester's, and it rests on a mapping the requester declares in its answer
contract. A modifier has no answer contract, so it has nowhere to declare one —
and the three ways an implementation might fill that gap (reject the modifier,
infer a mapping, invent a policy-side field) are three different behaviours from
one specification. A modifier narrowing an `enum` is therefore rejected as an
implementation error, exactly as a modifier that subsets is, until the question
is decided. Every other shape's modifier rule is unaffected.

**Capacity comes from the coarsened cardinality**, which is the label set's
size, looked up in the registry entry's capacity table as any varying
cardinality is ([`registry/README.md`](../registry/README.md)). A responder
never computes it, and never takes it from the request. An entry whose `enum`
domain may be coarsened therefore carries a table over every reachable label
count, not a single value — a registry-format consequence of this rule, not a
new mechanism.

## 4. Processing order

Order is a security property, not an implementation detail. It determines what
work an unauthenticated party can make a responder do, and what an attacker
learns from *which* step rejected.

A conforming responder processes in this order:

| # | Step | Why here |
|---|---|---|
| 1 | Parse the **envelope**; reject oversized or malformed input | Before any allocation on attacker-controlled data. |
| 2 | *Optional:* shed obviously stale traffic using `routing.expires_at` | Load shedding only. **Never a security decision** — `routing` is advisory. |
| 3 | Read the suite identifier; reject if below the verifier's minimum acceptable policy | The sender's declared suite selects how to verify, so it is read before verification — but it is checked against local policy, never trusted. Prevents algorithm-confusion and downgrade. |
| 4 | Resolve the key; **verify the signature over the exact signed bytes** | **Nothing below this line runs for an unauthenticated request.** |
| 5 | Parse the verified core object | Parsing happens *after* verification, so parser behaviour is outside the security boundary. |
| 6 | Expiry and clock-skew check — authoritative | The signed value governs; step 2 was advisory. |
| 7 | Delegation verification | Establishes the agent acts for the principal. |
| 8 | `routing` / `signed` consistency | Each projected field must equal the verified object's **exactly, with no coercion** — same type, same value, and for a string the same characters. No normalizing, no re-parsing a value into another form to decide it matches. §2.2's single timestamp spelling is what makes that decidable for `expires_at`, which would otherwise be two spellings of one instant and a disagreement about whether they disagree. Any difference is tampering. Reject; do not reconcile. |
| 9 | Replay-cache check | After signature, so unauthenticated traffic cannot pollute the cache. |
| 9a | **Rate-limit check** (§9.1) | After the replay check, so an idempotent retry returns its cached outcome without consuming rate budget. Before registry resolution, so **every** authenticated request counts identically — see below. |
| 10 | Registry: predicate known, version known, not revoked, digest pinned | Fails closed on anything unrecognized. |
| 11 | Public context validated against the entry's **input schema** | Schema comes from the registry, not the request. |
| 11a | Public context checked against the entry's **other constraints** — those its input schema cannot express | A different mechanism, so a separate step. See below. |
| 12 | Answer contract no broader than the registry entry | Q2D-C-02. |
| 13 | Requested assurance profile supported | Refuse rather than downgrade. |
| 14 | Policy evaluation → `allow` / `deny` / `escalate` + modifiers | First step that consults policy authorities. |
| 15 | Budget: sufficient capacity for the computed debit | Before private access, so exhaustion never reads data. |
| 16 | **Private input accessed; predicate evaluated** | Everything above gates this line. |
| 17 | Output validated against the effective domain | Q2D-C-03. Fails closed. |
| 18 | Budget debited | Once, idempotently. |
| 19 | Receipt constructed; response signed | Q2D-C-10. |

Steps 9a and 11a are lettered rather than numbered because the step numbers are
cited throughout this repository and renumbering them silently would be worse
than an irregular label.

**Step 11a is separate from 11 because they are different mechanisms.** Step 11
runs a schema the registry supplies, and an implementation satisfies it by
validating a document. An entry may also carry constraints no JSON Schema can
express — a minimum duration, a relationship between two fields, a bound that
depends on a value — and checking those is predicate-specific logic rather than
schema validation. Folding them into one step would let an implementation
satisfy §4 by running a validator and stopping, and would leave a conformance
vector unable to say which of the two rejected. Its placement is not arbitrary
either: after 11 because the schema is the cheaper check and establishes the
shape the constraints then assume, and before 12 because both ask whether the
request is within what the entry permits.

**Its position is a security property, not a convenience.** The rate limit is
keyed on the **relationship** the budget is keyed on — requester relationship and
subject — and on nothing else. It deliberately does *not* use the full budget key
(§9.1, [`terminology.md`](terminology.md) §6), because sensitivity class comes
from the registry entry and is not known until step 10. A limiter placed after
registry resolution would count only requests that resolved a predicate, leaving
requests for unknown predicates unlimited — and *that difference is itself an
oracle*: a requester that finds one predicate rate-limited and another unlimited
has learned which one this custodian carries, which is the disclosure step 10's
uniform failure exists to prevent.

Counting every authenticated request identically is what keeps the limiter from
becoming the thing it was introduced to close.

Four invariants follow:

- **Steps 1–15, and the lettered steps among them, complete before any
  private input is read.** A denial at any of
  them is reachable without touching protected data.
- **Rate limiting counts authenticated requests, not outcomes.** It runs before
  the responder knows what was asked, so its state cannot vary with the answer,
  the predicate, or the policy decision.
- **The core object is parsed only after its signature verifies** (step 5). An
  attacker cannot reach the JSON parser for the security-relevant object without
  a valid signature.
- **The external response must not reveal which step failed** where the
  sensitivity class requires normalization (Q2D-C-08). Internal audit records
  the true cause; the wire does not.

Step 17 failing is an implementation or integrity error, not a policy outcome.
It is logged as such, and the runtime must not serialize an exception carrying
private input.

### 4.1 The requester's order

The steps above bind a responder. A requester processing a **response** is bound
by the orderings below. They are normative for the same reason: two requesters
ordering these differently would both satisfy CC-1's obligations while one of
them parses attacker-controlled bytes before authenticating them, and a
conformance vector cannot assert an order the model does not state.

This is deliberately shorter than the responder's list. It names the orderings
whose violation is a vulnerability, not every action a runtime performs.

| # | Step | Why here |
|---|---|---|
| 1 | Parse the **envelope**; reject oversized or malformed input | Before any allocation on attacker-controlled data. |
| 2 | Read the suite identifier; reject if below the requester's minimum acceptable policy | Symmetric to responder step 3. A requester that accepts any suite the responder chose has no floor. |
| 3 | Resolve the responder key; **verify the signature over the exact signed bytes** | **Nothing below this line runs for an unauthenticated response.** |
| 4 | Parse the verified response object | After verification, so parser behaviour is outside the security boundary. |
| 5 | Check the response binds the query that was sent | Q2D-C-05. A valid signature over *some* exchange is not evidence about *this* one. |
| 6 | Read `status`, and branch on it as a closed set | An `escalate` or a `deny` is never coerced into an answer. See §5.3. |
| 7 | Verify the receipt | Q2D-C-10. Every outcome carries one (§6); a signed response with no receipt is rejected, not accepted with a check skipped. |
| 8 | Check the result lies within the domain that was requested | Directional check. The requester cannot verify the *effective* domain — see below. |
| 9 | Release the semantic answer to the caller | Nothing above may be skipped to reach this line. |

Three invariants follow:

- **The response object is parsed only after its signature verifies** (step 4),
  the same boundary step 5 sets on the responder side.
- **No part of a response reaches a caller before step 9.** A runtime that
  streams, logs, or previews a result while verification is still running has
  released an unauthenticated answer, whatever it does afterwards.
- **The three statuses are exhaustive and non-coercible.** A requester that maps
  an unrecognized status onto a default has built a path by which a future status
  is read as an answer.

Step 8 is a check against the **requested** domain, not the effective one: §5.1
carries `effective_contract_digest` rather than the effective domain itself, so a
requester can detect that its contract was narrowed but cannot independently
validate the result against what was authorized. That is a deliberate boundary.
Bounded output (Q2D-C-03) is a responder-side claim resting on a trusted
computation executor ([`../threat-model/trust-matrix.md`](../threat-model/trust-matrix.md)
§4), and echoing the effective domain would not defend against the adversary that
defeats it while disclosing to every requester exactly which modifier policy
applied.

## 5. Response

### 5.1 answer

| Field | Meaning |
|---|---|
| `status` | `answer` |
| `result` | The bounded semantic result, conforming to the effective domain. |
| `effective_contract_digest` | What was actually authorized — may be narrower than requested. |
| `assurance.profile` | The profile actually used. Never a silent downgrade. |
| `assurance.executor` | Identity of the computation executor. |
| `evidence` | Reference or compact object, where the profile carries one. |
| `receipt` | §6. |
| `signature` | Covers all of the above. |

**Exactly these fields, and no others**, with one conditional: `evidence` is
present where the assurance profile in force carries one and absent where it
does not. That conditionality is part of the enumeration rather than an
exception to it — the profile is named in the same response, in
`assurance.profile`, so the field set is determined by something the recipient
can already see. Adding a field, or making an existing one conditional on
anything else, is a specification change.

### 5.2 deny

| Field | Meaning |
|---|---|
| `status` | `deny` |
| `external_reason` | The **normalized class**, not the true cause. |
| `receipt` | The **reduced shape** — §6 is the authoritative field list. |
| `signature` | Covers all of the above. |

**Exactly four fields, and no others.** Adding one — even an optional one — is a
specification change, for the reason §6 gives about the receipt this response
carries: a field present for some causes and absent for others reintroduces the
distinction normalization removes, and the presence pattern alone is enough to
partition the class.

The closure is what makes the size requirement below structural rather than
aspirational. A field set that is not enumerated cannot be size-bounded, and
uniformity that rests on every implementer's care is not uniformity.

Within a sensitivity class configured for normalization, `external_reason`,
response size, and retry semantics are identical for absent data, policy
refusal, budget exhaustion, rate-limit rejection (§9.1), unsupported predicate,
failed freshness, and internal escalation. **A denial carries no retry metadata,
from any source, for any cause.** There is no field for it, so a value a rate
limiter could otherwise supply has nowhere to go — which is stronger than a rule
requiring such a value to be uniform, and removes what would otherwise be a
correct-but-fragile path one commit away from partitioning the class.

### 5.3 escalate

An authorized human or policy authority must decide before release. Two modes,
and the choice is itself a policy decision.

**Explicit escalation** returns exactly five fields, and no others:

| Field | Meaning |
|---|---|
| `status` | `escalate` |
| `pending_token` | Opaque. Carries no information about the decision pending. |
| `expires_at` | A timestamp — §2.2. |
| `receipt` | The **reduced shape** — §6, with `decision_class: escalate`. |
| `signature` | Covers all of the above. |

It carries **no `external_reason`**: that field names a normalized class, and an
explicit escalation is **not** denial-normalized and must never be described as
such. Adding a field here is a specification change, as it is for §5.2 — the
reasoning is weaker for this shape, since it is not in a normalized class, but
having one response in §5 that may grow arbitrary fields defeats the enumeration
for the others by giving a producer somewhere to put them.

This reveals that a relationship, record, or applicable policy path may exist.
Use only where that disclosure is acceptable.

An explicit escalation **carries a receipt**: the reduced shape §5.2 defines,
with `decision_class: escalate`. Q2D-C-10 binds every exchange, and an escalated
exchange that produced no evidence it happened would be an unstated exception to
it. There is no uniformity cost, because explicit escalation is not in a
normalized class.

**Opaque escalation** returns the same normalized envelope as §5.2 — the same
four fields, `status: deny` among them, and **including its receipt**, which is
the ordinary deny receipt and carries the ordinary deny `decision_class`. It is a
denial on the wire in every respect, which is the whole of what makes it
opaque. An opaque escalation must not be distinguishable from any other
outcome in that class by its receipt any more than by its response. This is the
boundary to get right: a receipt that recorded `escalate` for an outcome the wire
made uniform would defeat Q2D-C-08 through the evidence attached to it, in the
one place nobody looks for a normalization leak.

The authority is prompted out of band. Then:

1. The original query stays idempotent — identical retries keep returning the
   cached normalized outcome, and **never** become an answer after approval.
2. On approval the responder records a time-bounded grant keyed to an
   **approval-scope digest** covering requester principal and agent, predicate
   and version, answer-contract digest, purpose, answer recipient, sink set, and
   public-context commitment — and excluding `query_id`, `nonce`, `issued_at`,
   and `expires_at`.
3. The requester submits a **fresh signed query** with new identifier and nonce
   but the same approval scope.
4. The responder revalidates registry state, delegation, policy, freshness,
   budget, and current data before answering, and issues a new receipt.

**A grant is single-use.** It is consumed by the first release made under it, and
a second fresh query in the same window escalates again. One approval authorizes
one answer.

The reason is what an approval interface can honestly convey. A prompt can say
*"tell them whether you are free on Thursday."* No prompt can convey *"and every
repetition of this question until the window closes"* to a person deciding in a
moment. Under a multi-use reading, the disclosure a single approval authorizes
would be bounded by the capacity budget rather than by the consent, and Q2D-C-09
was never intended to be that bound. A deployment wanting standing permission
expresses it as a policy rule, where it is evaluated at step 14, recorded in the
audit, and visible as a rule rather than as the residue of a prompt somebody
answered once.

The cost is real and is the safe direction to fail in: a transient failure
between approval and the fresh query costs another approval.

The resulting unavailable-to-answer transition is a **residual timing and state
oracle**. It is named, not hidden. A binding may define authenticated push
delivery instead, but must not mutate the cached result of an identical retry.

## 6. Receipt

Binds one exchange (Q2D-C-10), in one of two shapes. **This is the authoritative
field list**; where any other document disagrees, this one governs.

**Full**, on an `answer`:

| Field | |
|---|---|
| `request_digest` | over the exact `signed` bytes received |
| `response_digest` | over the response's **semantic content** — result, effective contract digest, assurance profile — **excluding the receipt and the signature**. See below |
| `predicate` | identifier and version |
| `entry_digest` | the resolved registry entry (§2.4.1) — *which definition* was used, not only which version |
| `effective_contract_digest` | what was actually authorized |
| `policy_version` | a digest of the effective rule set |
| `release_shape` | the effective domain's shape |
| `assurance_profile` | the profile actually used |
| `signature_suite` | so the receipt stays assessable after that suite is deprecated |
| `disclosure_capacity_debit_millibits` | integer |
| `decided_at` | A timestamp — §2.2 |
| `responder` | the computation executor's identity |

**Reduced**, on a `deny` and on an explicit `escalate` — exactly five fields, and
no others:

`request_digest` · `decision_class` · `decided_at` · `responder` ·
`signature_suite`

The reduced shape is short by design, and its length is load-bearing: none of its
fields is variable-length — `decided_at` included, which is why §2.2 fixes one
timestamp spelling — so byte-length uniformity across every cause in a
normalized class follows from the shape rather than from a check (Q2D-C-08).
**Adding a field to it — even an optional one — is a specification change**, since
a field present for some causes and absent for others reintroduces the
distinction normalization removes. In particular it never names the predicate.

`response_digest` cannot be taken over the exact response bytes, and the reason
is structural rather than a choice: the receipt travels **inside** the response
and carries this digest, so a digest over the whole response would have to include
itself. Excluding the receipt and the signature makes it well-defined,
non-circular, and computable before the receipt exists. It is the one digest in
the protocol taken over a sub-object rather than over received bytes, so it needs
a canonical production profile where `request_digest` does not.

Its purpose is standalone verification: when a receipt travels with its response
the signature already binds the two, and this digest earns its place only when an
auditor holds a receipt separately and needs to confirm which response it
corresponds to.

A requester acknowledgment field is **reserved and not implemented** in 0.1.

Every response to a query therefore carries evidence that the exchange occurred,
which is what Q2D-C-10 claims.

**"Every response" means every response to a query.** A binding may define
auxiliary operations that are not exchanges — polling an escalation is the one
0.1 anticipates (§5.3) — and those are not responses in this sense: they answer
*has the outcome changed?* rather than *what is the answer?*, and there is no
exchange for them to bind. A binding defining one must say so explicitly, and
must not attach a receipt that binds nothing.

The receipt is deliberately **smaller than the local audit event**. Diagnostic
and policy detail stays local and is not disclosed to the requester by default.

## 7. Idempotency and replay

An identical retry — same signed `query_id` and `nonce` — returns the same
cached outcome. It must not debit the budget twice, and must not transition from
a normalized outcome to an answer.

A changed purpose, sink set, public context, predicate version, or answer
contract is a **different request** requiring a new signature and a new policy
decision, even when the approval-scope digest matches.

That last clause is a **floor, not a description of the current digest.** Under
§5.3's field list every item it names is already covered by the approval-scope
digest, so changing one necessarily changes the digest and it cannot match —
the clause is inert today. It is stated anyway because the field list is parked
(§9) and may yet be narrowed, and these five must remain request-distinguishing
whatever that list settles on. **Do not infer a narrower digest from it.** A
digest that omitted, say, the sink set would let an approval granted for one
delivery path satisfy a fresh query naming another.

## 8. Versioning

Core protocol, bindings, assurance profiles, registries, and implementation
packages version independently. A query and receipt bind the core version,
predicate version, registry digest, and assurance profile so that later code or
registry updates cannot reinterpret an earlier exchange.

## 9. Parked — not decided here

These are open in the technical report's Appendix C and stay open. Recorded so
that no implementation quietly settles them by accident.

| Open item | Current leaning | Blocked on |
|---|---|---|
| **Which identity profile, if any, is mandatory to implement** | None mandatory in 0.1 | A second profile existing to compare against |
| **Approval-scope digest field list** | The seven fields in §5.3 | Grant lifetime and revocation semantics |
| **Grant lifetime** | Required configuration, no default | Operating experience |
| **Capacity calculation for `object` outputs** | Registry supplies an upper bound from field domains, precision, and length | A formal calculation |
| **Timing and padding requirements** | None normative in 0.1 | A defined indistinguishability property and its tests |

An implementation may choose any of these. It must not describe its choice as
the Q2D answer until this document records it.

**Resolved since the first draft of this document.**

- **Serialization and the signature container.** The envelope in §2.1 signs exact
  transmitted bytes, so canonicalization is not on the security path, and
  algorithms are named by suite rather than fixed —
  [`crypto-suites.md`](crypto-suites.md) carries the registry, the
  mandatory-to-implement suite, and the downgrade rules.
- **The identity/delegation core-vs-profile boundary.** §2.3 defines the three
  interfaces; profiles supply the technology. Only the mandatory-profile question
  above remains.
- **Whether `deny` and `escalate` debit the budget.** They do not — see below.
- **Grant multiplicity.** Single-use, §5.3.

### 9.1 `deny` and `escalate` do not debit

Neither a denial nor an escalation debits the disclosure-capacity budget. The
probing they would otherwise permit is bounded by a **rate limit** — a separate
mechanism, with its own units, checked at step 9a, and carrying no claim.

**It is keyed on the relationship, and on nothing finer.** The budget key
additionally carries sensitivity class and sink set; the rate limit deliberately
does not, because those are known only after registry resolution and a limiter
that counted only resolved requests would leave unknown predicates unlimited —
a difference a requester can measure, and therefore an existence oracle. See §4.

The reason is that the two mechanisms measure different things. Q2D-C-09 accounts
for *disclosure*, in millibits of answer alphabet. A denial discloses nothing
from the answer alphabet; what it can leak is policy structure, which has no
bit-count in this model. Debiting it would make
`disclosure_capacity_debit_millibits` a number that no longer means what
Q2D-C-09 says it means. Debiting would also let any party that can reach a
custodian spend a subject's budget without ever receiving an answer, so that
legitimate requesters are refused — a harm to a third party that no claim covers.

Two requirements come with this, and without them the decision is unsafe:

1. **The rate limit is required configuration with no default.** A responder
   whose rate limit is unset does not conform. Not debiting denials while also
   not limiting them is unbounded free probing.
2. **A rate-limit rejection is normalized**, indistinguishable from every other
   outcome in its class. It carries no retry metadata at all, because §5.2's
   response has no field for one — which matters most here: a limiter's natural
   output is a time to wait, that value is cause-specific by construction, and
   this is the one cause that always has such a value available. A
   distinguishable rate-limit response is the oracle the limit was introduced to
   prevent; it would move the leak rather than close it.

   A rejection at step 9a precedes registry resolution, so the responder does not
   yet know the predicate's sensitivity class and cannot select a per-class
   external value. It uses the deployment's **default normalized class**, which
   is the same value an unknown predicate produces at step 10 — the two must not
   be distinguishable, or the limiter reveals that resolution was never reached.
