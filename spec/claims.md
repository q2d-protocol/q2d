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
answer domain — its shape, cardinality, precision, field allowlist, and maximum
serialized size.
**Holds when.** Q2D-C-02 holds and output validation runs before serialization.
**Enforced by.** Output validation against the effective domain; fail-closed
when the result falls outside it.
**Fails if.** Validation is skipped for a `detail` field; an exception path
serializes private input; a structured output escapes cardinality limits.
**Not.** A claim that a bounded answer is harmless. One bit can reveal a
consequential fact — capacity is not severity. See Q2D-NC-07.
**Verified by.** `conformance/out-of-domain-result`, `conformance/error-path-leakage` — planned.

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
An identical retry returns the cached outcome and does not debit the disclosure
budget again.
**Holds when.** The replay cache covers the expiry window and nonces have
sufficient entropy.
**Enforced by.** Nonce, issue time, expiry, and query identifier under
signature; responder replay cache; idempotent retry handling.
**Fails if.** Clock skew exceeds tolerance; the cache is evicted early; keys are
compromised.
**Not.** Prevention of fresh repeated queries by a legitimate requester — that
is Q2D-C-09's problem, and it is a throttle, not a bar.
**Verified by.** `conformance/replay`, `conformance/duplicate-debit`,
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
`conformance/sybil-relationship` — planned.

### Q2D-C-10 — Exchange-bound accountability

**Claim.** Every outcome carries a receipt binding it to one exchange, and the
receipt's contents depend on the outcome:

- an **`answer`** binds the request digest, response digest, predicate and
  version, registry-entry digest, effective answer-contract digest, policy
  version, release shape, assurance profile, capacity debit, decision time, and
  responder identity;
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
**Holds when.** The responder issues a receipt for every outcome and retains
detailed audit locally ([`core-model.md`](core-model.md) §5.2, §5.3, §6).
**Enforced by.** Receipt construction under the response signature.
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

| ID | Q2D does not claim |
|---|---|
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

Claims of being "the first" anything require a literature and patent search that
has not been performed.

---

## Traceability

Every claim above must map to at least one executable check before the project
describes Phase 1 as complete. Until the conformance suite exists, `planned`
identifiers are placeholders that name the test, not evidence that it passes.

A claim with no passing test is a design intention. This document distinguishes
the two, and any status page derived from it must preserve that distinction.
