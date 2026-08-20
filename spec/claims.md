# Q2D Claims and Non-Claims — version 0.1

**Protocol version:** 0.1 (pre-release)
**Document status:** Specification spine — working draft, not yet a normative specification.

Every security or privacy property Q2D 0.1 asserts, with the assumptions it
rests on, the mechanism that enforces it, the conditions under which it fails,
and the overstatement it must never be read as.

A claim absent from this document is not a Q2D claim. If marketing copy, a
README, a talk, or a later draft asserts something that is not here, the
assertion is wrong or this document is out of date — and the burden is on the
assertion.

**The property the rest of this document qualifies is
[Q2D-C-03](#q2d-c-03--bounded-output).** A custodian returns a value that must lie
inside a domain defined by a **third artifact** — a registry the custodian pinned
— rather than by the party producing the answer. Every other claim here either
establishes that bound, authenticates it, or accounts for it.

Terms: [`terminology.md`](terminology.md). Boundaries: [`scope.md`](scope.md).
Claim *language* — which words to use for each of these — is
[`terminology.md`](terminology.md) §9.

Where this document and the technical report disagree, this document governs.

---

## How to read an entry

| Field | Means |
|---|---|
| **Claim** | What holds. |
| **Holds when** | Assumptions. If any is false, the claim says nothing. |
| **Enforced by** | The mechanism. Not a promise, not a policy — a thing an implementation does. |
| **Fails if** | Concrete conditions that break it. Not exhaustive. |
| **Not** | The adjacent overstatement this claim gets confused with. |
| **Verified by** | The conformance test. `planned` means the suite does not exist yet. |

Claim identifiers are stable. A claim that is withdrawn keeps its identifier and
is marked withdrawn rather than reused.

---

## Source-side claims

These hold for a conforming responder at the `authenticated-answer` profile.
They do not depend on requester-side containment.

**Q2D-C-03 is the one to read first.** Q2D-C-02 is what makes it non-trivial —
the domain comes from the registry rather than from the responder's own
declaration — and Q2D-C-10 is what makes it checkable afterwards. The rest
support those three.

### Q2D-C-01 — Pre-evaluation commitment

**Claim.** The requester commits to the predicate and version, public context,
answer contract, purpose, answer recipient, permitted sinks, and freshness
before the responder evaluates policy or reads private input.
**Holds when.** The requester signature covers those fields and the responder
verifies it before proceeding.
**Enforced by.** Signature over the canonical request; responder ordering —
validation precedes private access.
**Fails if.** The responder evaluates before verifying; a binding permits fields
to be supplied out of band; the requester key is compromised.
**Not.** Evidence that the declared purpose is honest. See Q2D-NC-02.
**Verified by.** `conformance/ordering`, `conformance/signature-coverage` — planned.

### Q2D-C-02 — Responder-owned domain validation

**Claim.** The effective answer domain is resolved by the responder from a
registry entry it trusts, narrowed by the requester's contract and policy
modifiers under [`core-model.md`](core-model.md) §3. A requester-asserted domain
is never trusted.
**Holds when.** The registry entry is authentic, unrevoked, and pinned; the
responder rejects unknown predicate versions and registry digests.
**Enforced by.** Registry pinning; signature over the manifest; fail-closed on
unknown version or digest; narrowing composition computed responder-side.

`answer_contract.coarsening` (`core-model.md` §2.5) is not an exception to this.
The requester declares a mapping; the responder **validates** it against the
registered domain under §3.2 and computes the effective domain itself. A
declared mapping is a request like any other field of the contract, and the
capacity debit still comes from the registry rather than from anything the
requester said.
**Fails if.** The registry signing key is compromised; an entry is wrong; the
responder accepts a requester-supplied domain as authoritative.
**Not.** A guarantee that the registered domain is *appropriate*. A registry can
publish a technically bounded predicate that is substantively excessive.
**Verified by.** `conformance/domain-understatement`, `conformance/domain-expansion`,
`conformance/unknown-registry-digest` — planned.

### Q2D-C-03 — Bounded output

**Claim.** An automatically released semantic result conforms to the effective
answer domain — its shape, cardinality, precision, and field allowlist — and to
the registry entry's `output_schema`, which bounds the length of every
variable-length value it can release ([`scope.md`](scope.md) §4.1).
**Holds when.** Q2D-C-02 holds; output validation runs before serialization; and
the entry's `output_schema` actually carries the bounds
[`scope.md`](scope.md) §4.1 requires — an entry admitting a string with no
`maxLength`, or a subschema with no `type`, bounds nothing, and this claim rests
on the registry being well formed as much as on the responder checking it.
**Enforced by.** Output validation against both, at
[`core-model.md`](core-model.md) §4 step 17; fail-closed when the result falls
outside either. The two are not redundant: the domain bounds which values may be
returned, and the schema bounds how long they may be — an `attribute` is
*released in full* and permits no narrowing, so only the schema bounds it. The
schema's own conformance to §4.1 is enforced at registry validation, before any
request reaches it.
**A consequence worth stating, because it is the reason this claim matters in
2026.** An adversarial instruction sitting in the custodian's data — a poisoned
record, a rewritten field, an injected string — **cannot be transmitted through
this interface**. The released value must lie inside the registered answer
domain, so where that domain is a `boolean`, a small `enum`, or a bounded
interval, there is no field an instruction can occupy.

**It can still influence the answer.** A poisoned record can flip a boolean, and
that flip crosses the interface because it is the value the requester asked for.
The distinction is between a **one-bit effect on a requested value** and a
**channel into the requester's context**, and only the second is closed.

**The bound is weakest where the release shape is widest.** An `object` release
with detail fields, or an `attribute` released in full, is bounded by the entry's
`output_schema` rather than by a small cardinality — which is why
[E-28](../docs/open-escalations.md) required that schema to bound every
variable-length value, and why the *Fails if* clause about an unbounded schema is
not a technicality.
**Fails if.** Validation is skipped for a `detail` field; an exception path
serializes private input; a structured output escapes cardinality limits; **or an
entry is admitted whose output schema leaves a variable-length value unbounded**,
which moves the failure from the responder to the registry without changing what
crosses the interface.
**Not.** A claim that a bounded answer is harmless. One bit can reveal a
consequential fact — capacity is not severity. See Q2D-NC-07. **Nor a claim
about prompt injection generally**: this closes the *response* channel, and the
tool-description channel is untouched — see Q2D-NC-14.
**Verified by.** `conformance/out-of-domain-result`, `conformance/error-path-leakage`, `conformance/over-schema-bound-result` — planned. The third is the `attribute` case: a result inside the effective domain and longer than its schema permits, which no other vector catches because every other bound is the domain's.

Registry-side, [`registry/validate.py`](../registry/validate.py) refuses an entry whose output schema leaves a variable-length value unbounded — the assumption above, checked rather than assumed.

### Q2D-C-04 — Source confinement

**Claim.** For the default bounded-answer profile, private input is not
serialized into the response. Only the bounded result, receipt, and permitted
public metadata cross the Q2D interface.
**Holds when.** The predicate is registered to return a bounded result rather
than raw data; the computation executor is uncompromised.
**Enforced by.** Local evaluation; response construction from validated output
only; error messages that carry no private values.
**Fails if.** A predicate is registered that returns source data; a diagnostic
path echoes input; the executor is compromised. See Q2D-NC-06.
**Not.** A claim that nothing is learned. The answer itself is a disclosure.
**Verified by.** `conformance/response-content`, `conformance/error-message-content` — planned.

### Q2D-C-05 — Request binding

**Claim.** An intermediary cannot alter the predicate, public context, purpose,
recipient, sinks, answer contract, freshness, or nonce without invalidating the
requester signature.
**Holds when.** The signature suite in force is sound and is at or above the
verifier's minimum acceptable policy; the signature covers every listed field.
**Enforced by.** Signing the exact transmitted bytes of the core object
([`core-model.md`](core-model.md) §2.1); verification before the object is
parsed; rejection when the advisory `routing` projection disagrees with the
signed object.
**Fails if.** A binding places a covered field outside the signed object; the
requester key or runtime is compromised; the suite is broken or the verifier
accepts one below its floor.
**Not.** Protection against a requester that signs a malicious contract itself.
**Verified by.** `conformance/field-tampering`, `conformance/routing-mismatch`,
`conformance/suite-downgrade` — planned.

### Q2D-C-06 — Response authentication

**Claim.** The responder signature binds the semantic result or denial status,
the effective answer contract, the receipt, and the request digest to the
computation executor's identity.
**Holds when.** The key-to-principal binding is sound under the selected
identity profile, and the signature suite in force is sound and at or above the
verifier's minimum acceptable policy.
**Enforced by.** Signature over the exact response bytes under a registered
suite; requester-side verification before the answer reaches the agent; the
receipt records which suite was used, so the response remains assessable after
that suite is deprecated.
**Fails if.** Executor keys are compromised; the identity profile misbinds a key
to a claimed principal; the suite is broken or accepted below the verifier's
floor.
**Not.** Proof that the predicate was executed faithfully, that the correct
record was selected, that the data was current, or that the underlying fact is
true. This is origin and integrity only. See Q2D-NC-01 and Q2D-NC-10.
**Verified by.** `conformance/response-signature`, `conformance/receipt-binding` — planned.

### Q2D-C-07 — Replay resistance

**Claim.** An intercepted request cannot be reused within the supported window.
An identical retry returns **the stored response bytes**, without re-evaluating
the predicate or reading private input again.

**The second sentence said *"and does not debit the disclosure budget again"***
until 2026-08-19. Q2D-C-09 is **not attempted in this release**, so there is no
budget and no debit; promising duplicate-debit protection for an unbuilt
mechanism would state more than the release can demonstrate. Returning the
stored bytes is the stronger property anyway and was always the observable —
nothing is regenerated, so two retries cannot differ, and where a budget exists
returning stored bytes is *why* it is not debited twice.
**Holds when.** The replay cache covers the expiry window and nonces have
sufficient entropy. **Both halves are supplied by different parties.** The
first is a responder's and [`freshness.md`](freshness.md) §1 makes it structural
— retention is derived from the window rather than set beside it, so a cache that
covers the window is the only cache the rule admits. The second is a
**requester's**, and no responder-side check establishes it: a responder holds
one nonce and no distribution, so it can enforce a length floor and nothing more
(§3 there). Sixteen zero bytes clear every check a responder can make.
**Enforced by.** Nonce, issue time, expiry, and query identifier under
signature; responder replay cache; idempotent retry handling; the bounds in
[`freshness.md`](freshness.md) §1.
**Fails if.** Clock skew exceeds tolerance; the cache is evicted early; keys are
compromised.
**Not.** Prevention of fresh repeated queries by a legitimate requester — that
is Q2D-C-09's problem, and it is a throttle, not a bar.
**Verified by.** `conformance/replay`, ~~`conformance/duplicate-debit`~~ — struck
2026-08 with the budget it would have measured; the stored-bytes property is what
`conformance/replay` asserts —
`conformance/expiry-skew` — planned.

### Q2D-C-08 — Denial normalization

**Claim.** Within a configured sensitivity class, a responder can map absent
data, policy refusal, budget exhaustion, rate-limit rejection, unsupported
predicate, failed freshness, and internal escalation onto one external class,
reducing explicit existence and policy oracles.
**Holds when.** The external envelope, its size, and its retry semantics are
identical for every internal cause in the class.
**Enforced by.** A **closed** external schema — `core-model.md` §5.2's four
fields and §6's five-field receipt, both of which state that adding a field is a
specification change; no retry metadata, because there is no field for one; no
private values in error strings.

Closure bounds the field *set*, and `core-model.md` §2.2's single timestamp
spelling bounds the one field whose length could otherwise vary, so **bounded
response size follows from the shape** rather than from what a deployment
happens to emit. Both are needed: the field list alone left `decided_at` free to
be six characters or one.
**Fails if.** Timing, traffic volume, consent notifications, rate limits, or
later state changes distinguish causes; a distinct `escalate` response is
returned inside a class requiring normalization.
**Not.** Wire-level indistinguishability. Q2D does not define or test a formal
indistinguishability property in 0.1. See Q2D-NC-05.
**Verified by.** `conformance/denial-uniformity`, `conformance/retry-metadata` — planned.

### Q2D-C-09 — Disclosure-capacity accounting

> **Not attempted in this release.** Deferred 2026-08-19, and the reason is a
> finding rather than a schedule: this claim measures a quantity that is not the
> one anyone is worried about. Its own *Fails if* list below already concedes that
> collusion, correlated predicates, auxiliary knowledge and cross-custodian
> spreading each defeat it — and no operator can say what a budget of *N*
> millibits permits or prevents.
>
> **What bounds probing instead is a required request quota**, keyed on the
> relationship, checked at §9.1's step 9a, with no default. That is a rate limit;
> it carries **no claim** and is not measured in these units, exactly as
> [E-01](../docs/open-escalations.md) decided when it introduced one.
>
> **The claim is kept rather than deleted**, because it is cited by
> [`core-model.md`](core-model.md) §2.5 — where the prohibition on subsetting is
> justified by it — and by `conformance-classes.md` CC-2 and CC-3, and by seven
> PRDs. It also remains the right claim to make if a deployment ever asks for a
> subject-level cap enforced in bits. Nothing below is withdrawn; it is unbuilt.

**Claim.** Each released finite-domain answer debits `log2(cardinality)` of the
**effective** domain from a policy-defined budget, computed by the responder.
Exhaustion escalates or denies.
**Holds when.** The budget key is meaningful for the deployment; the relationship
is costly enough to establish that recreation is not trivial; and the effective
domain cannot be narrowed into one whose out-of-domain outcome is itself
informative — which is why [`core-model.md`](core-model.md) §2.5 prohibits
subsetting.
**Enforced by.** Responder-side debit from the registry-verified effective
domain; any debit or domain size asserted by a requester is ignored.
**Scope.** Only a released answer debits. A denial or an escalation discloses
nothing from the answer alphabet and debits nothing
([`core-model.md`](core-model.md) §9.1); the probing they would permit is bounded
by a separate rate limit, which carries no claim and is not measured in these
units.
**Fails if.** Requesters collude or recreate relationships; correlated
predicates or auxiliary knowledge defeat the accounting; queries are spread
across custodians; **the required rate limit is unconfigured**, leaving denials
unbounded.
**Not.** A differential-privacy, inference, or posterior-risk guarantee. It
measures the capacity of an answer alphabet, not what an adversary learned. See
Q2D-NC-04.
**Verified by.** `conformance/budget-debit`, `conformance/adaptive-probing`,
`conformance/sybil-relationship` — **not attempted in this release**. The
`registry/` vectors that cited this claim no longer do: they asserted a debit
value, and there is nothing computing one.

### Q2D-C-10 — Exchange-bound accountability

**Claim.** Every outcome carries a receipt binding it to one exchange, and the
receipt's contents depend on the outcome:

- an **`answer`** binds the request digest, response digest, predicate and
  version, registry-entry digest, effective answer-contract digest, policy
  version, release shape, assurance profile, decision time, and responder
  identity;
- a **`deny`**, and an **explicit `escalate`**, bind the request digest, decision
  class, decision time, responder identity, and signature suite — and nothing
  else.

**The reduced shape binds less on purpose, and the claim is not making a larger
statement about it.** Its fields are exactly those that carry no information
about the request beyond the fact that it occurred: a denial receipt that named
the predicate would partition denials by predicate, defeating Q2D-C-08 through
the evidence attached to the response. What a reduced receipt attests is *this
exchange happened, at this time, and produced this external class* — which is the
accountability a denial can honestly support.
**The capacity debit left this list on 2026-08-19**, with Q2D-C-09. A field whose
only available value is zero is a lie in waiting — a reader seeing `0` would
conclude the answer disclosed nothing. The list is closed
([E-22](../docs/open-escalations.md)), so removing a field is a specification
change and is recorded as one. If a disclosure-magnitude field is ever wanted, it
gets a **new name and its own reasoning**, rather than this one restored with a
different meaning.
**Holds when.** The responder issues a receipt for every outcome and retains
detailed audit locally ([`core-model.md`](core-model.md) §5.2, §5.3, §6).
**The local audit is load-bearing, not incidental**: a receipt with no retained
audit behind it satisfies half of this claim.
**Enforced by.** Receipt construction under the response signature.

**A consequence: a silently changed predicate fails a check rather than quietly
meaning something new.** The receipt binds `entry_digest`, and
[`core-model.md`](core-model.md) §2.4.1 makes an entry's digest change when its
definition changes. A custodian that swapped a predicate's meaning between two
exchanges produces a receipt naming a digest the requester did not expect.

**This requires the requester to know what to expect**, which means obtaining the
entry independently rather than from the custodian answering the question. That
is deliberate — a discovery endpoint would hand over the entry the check exists
to compare against — and it is a real operability cost, not a free property: two
parties on different manifest versions fail in a way neither can diagnose from
the wire.
**Fails if.** A binding omits receipt fields; audit and receipt diverge; an
outcome is returned with no receipt at all; a reduced receipt is read as
attesting to anything an answer receipt attests to.
**Not.** Evidence that the underlying facts are true, that a legal basis was
valid, or that a recipient honoured a retention promise. A receipt records that
a runtime processed an exchange.
**Verified by.** `conformance/receipt-fields`, `conformance/receipt-audit-consistency` — planned.

---

## Composition claim

### Q2D-C-11 — Binding equivalence

> **Not attempted in this release.** Deferred 2026-08-19. Binding equivalence is a statement **between** bindings, and this release builds one — MCP. A second binding is what would make it testable. Kept rather
> than deleted: it is the claim to make when the work exists.

**Claim.** Two conforming bindings carrying the same core exchange preserve
identical semantics: identity and delegation, predicate and registry reference,
answer contract, purpose and delivery, freshness and replay, response status,
evidence and receipt binding, and idempotency.
**Holds when.** Each binding round-trips the signed core object without rewriting
covered fields.
**Enforced by.** Binding conformance tests over a shared vector set.
**Fails if.** A transport lacks a field and the binding drops it silently rather
than failing.
**Not.** A claim that every transport offers equivalent metadata privacy.
Endpoints, traffic patterns, and relationship graphs differ per transport.
**Verified by.** `conformance/binding-equivalence` — planned.

---

## Requester-side claims — conditional

These hold **only** under the `q2d-contained-runtime-0.1` profile. A deployment
without it may claim everything above and nothing below.

### Q2D-C-12 — Evidence segregation

> **Not attempted in this release.** Deferred 2026-08-19. Conditional on `q2d-contained-runtime-0.1`. The contained requester runtime is deferred, CC-10 is not built, and there is no model in the loop to segregate evidence from. Kept rather
> than deleted: it is the claim to make when the work exists.

**Claim.** Signatures, credentials, proofs, policy traces, and receipts are
verified in the requester runtime and do not enter model context. The agent
receives the semantic answer and the minimum metadata policy permits.
**Holds when.** The runtime, not the model, constructs and verifies protocol
messages.
**Enforced by.** Verification outside model context; semantic-answer projection
into the tool result.
**Fails if.** A framework writes full tool results to a trace the model can read
back; a binding exposes evidence as an ordinary model-visible result.
**Not.** A claim that the semantic answer is insensitive. It reduces material
available to injection; it does not declassify the answer.
**Verified by.** `conformance/model-context-content` — planned.

### Q2D-C-13 — Conditional flow confinement

> **Not attempted in this release.** Deferred 2026-08-19. Same. Confining answer-derived flows requires **every** relevant sink to be mediated, and this release mediates none. Kept rather
> than deleted: it is the claim to make when the work exists.

**Claim.** Answer-derived machine outputs reach only sinks permitted by the
effective contract and local policy.
**Holds when.** **Every** relevant sink is mediated — model endpoints, tools,
logs, traces, memory, analytics, files, queues, network egress — and labels
propagate conservatively through transformations.
**Enforced by.** Information-flow labels; sink inventory; mediation of tool and
network calls; fail-closed on lost provenance.
**Fails if.** Any sink is unmediated. A plugin opening an untracked socket, an
uncontrolled trace, or model-provider retention beyond policy each defeat it for
that path.
**Not.** A claim that prompt injection cannot exfiltrate. It bounds what an
injected model can leak to what it legitimately received, and only to approved
destinations — and only under complete mediation. See Q2D-NC-11.
**Verified by.** `conformance/sink-mediation`, `conformance/injection-egress` — planned.

---

## Standing non-claims

True at every version and every assurance profile. These are not caveats on the
claims above; they are positions the project holds.

**The first two are the ones most likely to be assumed**, and they are placed
first for that reason rather than by number. Q2D-NC-14 and Q2D-NC-15 were added
in 2026-08 when Q2D-C-03's bounded-output property was stated in terms of
injection, because that framing invites both misreadings.

| ID | Q2D does not claim |
|---|---|
| **Q2D-NC-15** | **That Q2D constrains a hostile custodian.** The threat model assumes a *participating* custodian and treats the requesting agent as untrusted; it is a way for an honest custodian to prove it is honest, not a way to constrain a dishonest one. A compromised or malicious server — the failure mode most reported against tool interfaces in 2026 — is outside it entirely. Q2D-C-03's bound is enforced *by* the custodian, at [`core-model.md`](core-model.md) §4 step 17, and a custodian that does not run it is not conforming and not detectable by this protocol. |
| **Q2D-NC-14** | **That a bounded answer domain prevents prompt injection.** It closes the **response** channel: an injected payload in the custodian's data has no field to occupy in a `boolean` or a small `enum`. It does not close the **tool-description** channel — a poisoned tool description, parameter schema, or registered question reaches model context untouched — and it does not stop a payload *influencing* the answer within its domain. See Q2D-C-03. |
| **Q2D-NC-01** | That the underlying facts are true, complete, current, or independently verified. A signature over a self-asserted attribute authenticates the assertion, not the fact. |
| **Q2D-NC-02** | That a declared purpose is honest, or enforceable once information reaches a human. |
| **Q2D-NC-03** | That a released answer can be retracted. Revocation governs future requests only. |
| **Q2D-NC-04** | Any formal inference-privacy guarantee. The capacity budget is not differential privacy and does not model an adversary's prior. |
| **Q2D-NC-05** | Wire-level indistinguishability of denials. Timing, size, notification, rate-limit, and state channels remain. |
| **Q2D-NC-06** | Protection against a compromised computation executor in Phase 1. It holds legitimate access to private input. |
| **Q2D-NC-07** | That a bounded answer is harmless, or that the chosen answer is globally minimal for the requester's task. |
| **Q2D-NC-08** | That a human who legitimately learns an answer will not remember or repeat it. |
| **Q2D-NC-09** | That a deployment is GDPR-compliant. Controller roles, lawful basis, and consent validity depend on actual processing activities. |
| **Q2D-NC-10** | That a Phase 1 signature is a zero-knowledge proof, or proof that the correct source data was used or the predicate faithfully executed. |
| **Q2D-NC-11** | That labels alone stop leakage when any sink, log, memory path, or side channel is unmediated. |
| **Q2D-NC-12** | Novelty for source-side predicate APIs, information-flow control, capability authorization, cumulative leakage budgets, selective disclosure, trusted execution, or tamper-evident logs. The contribution is the composition. |
| **Q2D-NC-13** | That a query is confidential from an intermediary. The 0.1 suite signs the payload and does not encrypt it, so a party holding the envelope reads every field of the core object — `routing`'s minimality (`core-model.md` §2.1) governs what is legible *without decoding*, which is a real difference and not a confidentiality boundary. A deployment needing one uses transport confidentiality or a suite 0.1 does not register. |

| **Q2D-NC-14** | *(stated first in this table — see above)* That a bounded answer domain prevents prompt injection. |
| **Q2D-NC-15** | *(stated first in this table — see above)* That Q2D constrains a hostile custodian. |

Claims of being "the first" anything require a literature and patent search that
has not been performed.

---

## Traceability

Every claim above must map to at least one executable check before the project
describes Phase 1 as complete. Until the conformance suite exists, `planned`
identifiers are placeholders that name the test, not evidence that it passes.

A claim with no passing test is a design intention. This document distinguishes
the two, and any status page derived from it must preserve that distinction.
