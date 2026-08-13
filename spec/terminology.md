# Q2D Terminology

**Protocol version:** 0.1 (pre-release)
**Document status:** Specification spine — working draft, not yet a normative specification.
**Supersedes:** all PAX-era vocabulary.

This document fixes the vocabulary of Q2D. Its job is narrow: prevent terminology
drift between the technical report, the normative core specification, the bindings,
and the reference implementation while those are being written.

It defines terms and identifiers. It does not define wire format, message
validation order, or conformance requirements. Those belong in:

| Document | Defines |
|---|---|
| `spec/scope.md` | What Q2D 0.1 covers and what is deferred. |
| `spec/claims.md` | Each claim, its assumptions, and its matching non-claim. |
| `spec/core-model.md` | Request and response envelopes; the `answer` / `deny` / `escalate` outcomes. |
| `spec/conformance-classes.md` | What an implementation must do to claim a class. |
| `threat-model/trust-matrix.md` | Trusted and untrusted components per property. |

Where this document and the technical report disagree, this document governs and
the report is to be corrected. Where this document and a later normative
specification disagree, the specification governs.

---

## 1. Requirement keywords

The key words **MUST**, **MUST NOT**, **REQUIRED**, **SHALL**, **SHALL NOT**,
**SHOULD**, **SHOULD NOT**, **RECOMMENDED**, **MAY**, and **OPTIONAL** are to be
interpreted as described in BCP 14 (RFC 2119, RFC 8174) when, and only when, they
appear in all capitals.

This document contains few such keywords by design. Terminology constrains
language; the core specification constrains behaviour.

---

## 2. Roles

A **role** is a function in an exchange, not a piece of software and not a legal
status. One process, device, or organization MAY hold several roles. Two roles
held by one party remain two roles, and the specification never assumes their
collapse.

| Term | Definition |
|---|---|
| **Requester principal** | The person, organization, or service on whose behalf the question is asked. The accountable party behind the request. |
| **Requester agent** | The planning or conversational software that proposes a query intent. May include a language model. Never assumed to enforce policy correctly. |
| **Requester runtime** | The trusted requester-side software that resolves identity, constructs and signs the answer contract, verifies the response, and stores the receipt. Distinct from the requester agent; this distinction is load-bearing. |
| **Data custodian** | The person or organization operating or controlling the protected source and authorizing a Q2D responder to access it. A party, not a program. |
| **Custodian runtime** | The custodian-side software implementing the Q2D responder: authentication, delegation resolution, freshness and replay checks, registry validation, policy invocation, evaluation, output validation, budget debit, receipt creation, signing. |
| **Computation executor** | The role, held by the custodian runtime in v0.1, that accesses private inputs, evaluates the predicate, validates the output against the effective answer domain, and signs the response. Named separately because later assurance profiles relocate it — to a proof system, a credential holder, or an attested environment — without changing the surrounding protocol. |
| **Data subject** | A person whom the protected data concerns. A data subject MAY be a policy authority, MAY be one input to policy, and MAY be neither. Never treat "data subject" and "policy authority" as interchangeable. |
| **Policy authority** | A party authorized — by the custodian, by law, by contract, by delegation, or by system design — to define a release policy applicable to a given source. There MAY be more than one. |
| **Answer recipient** | The initial process or principal that receives the bounded semantic answer after the requester runtime has verified the response. |
| **Sink** | Any destination that may receive the answer or a value derived from it. See §7. |
| **Credential issuer** | An optional party attesting to facts or attributes consumed by a credential-backed assurance profile. |
| **Auditor** | An optional party authorized to verify receipts, policies, evidence, or implementation conformance. Also **verifier**; the two are synonyms in Q2D and `auditor` is preferred. |

### 2.1 Role collapse

Deployments collapse roles routinely. The vocabulary does not.

- **Personal agent.** One person's device may hold data subject, data custodian, policy authority, and computation executor simultaneously.
- **Enterprise.** The company is custodian and policy authority; an employee or customer is the data subject and may hold no authority at all.
- **Credential-backed.** An external issuer attests a fact, a holder controls presentation, and the custodian evaluates a predicate over the credential.

### 2.2 Resolved ambiguity: custodian runtime and computation executor

The technical report uses **custodian runtime** in its architecture section and
**computation executor** in its role table for overlapping responsibilities. They
are not synonyms. The custodian runtime is the deployed component; the computation
executor is the role that touches private input and signs the result. In v0.1 the
custodian runtime holds that role, so the terms coincide in practice — but
statements about *trust* MUST name the computation executor, because that is what
a future profile displaces.

---

## 3. Protocol objects

| Term | Definition |
|---|---|
| **Predicate** | A registered, versioned, bounded computation over private input and public context. Not a free-form expression and not arbitrary code. |
| **Predicate registry** | The trusted, versioned source of predicate definitions. A logical trust component, not necessarily one global service. In v0.1 it is a signed manifest distributed with the application, whose signing key and digest the custodian pins locally. |
| **Registry entry** | One predicate definition: identifier, version, input and public-context schemas, output schema, canonical answer domain, release shape, capacity calculation, sensitivity classification, freshness semantics, supported assurance profiles, provenance and revocation metadata, and test vectors. |
| **Public context** | Requester-supplied input that is not confidential — the proposed menu, the candidate week, the threshold. Travels in the query or as a digest. |
| **Private input** | The custodian-held data the predicate reads. Does not cross the Q2D interface. |
| **Answer contract** | The requester's pre-evaluation commitment: release shape, output schema, requested answer domain, maximum cardinality, allowed detail fields, precision, the `enum` coarsening mapping where one is requested ([`core-model.md`](core-model.md) §3.2), and disclosure class. Submitted before the custodian evaluates policy or private data. **An answer contract is not permission.** It is an input to policy evaluation. |
| **Query** | The signed request envelope carrying protocol metadata, principals and delegation, predicate reference, answer contract, purpose, delivery, and freshness. |
| **Response** | The signed reply to a query, carrying one outcome — `answer`, `deny`, or `escalate` — and **always a receipt**: the full shape for an answer, the reduced shape for a denial or an explicit escalation ([`core-model.md`](core-model.md) §6). A binding's auxiliary operations, such as polling an escalation, are not responses in this sense and carry no receipt. |
| **Disclosure receipt** | The object binding one exchange, in one of two shapes. **Full**, on an `answer`: request digest, response digest, predicate and version, registry-entry digest, effective answer-contract digest, policy version, release shape, assurance profile, disclosure-capacity debit, decision time, and responder identity. **Reduced**, on a `deny` or an explicit `escalate`: request digest, decision class, decision time, responder identity, and signature suite — and deliberately nothing more, since a denial receipt naming the predicate would partition denials by predicate and defeat denial normalization. Either shape is evidence that a runtime processed and authenticated an exchange — **not** evidence that the underlying facts are true, that a legal basis was valid, or that a retention promise was kept. |
| **Declared purpose** | What the requester states the answer is for. Signed, therefore attributable. Not proof of intent. |
| **Authorized purpose** | What the responder actually permitted. Recorded in the receipt. Distinguish from declared purpose in every message and every document. |

---

## 4. Release shapes

A **release shape** describes *what the recipient can learn*. It is independent of
assurance profile (§5); the two dimensions never form a single ladder.

Identifiers are stable and lowercase. The `q2d:shape:` prefix is used where a
namespaced form is required.

| Identifier | Meaning |
|---|---|
| `boolean` | One of two values. |
| `enum` | One value from a finite registered set. |
| `scalar` | A bounded integer or number at registered precision. |
| `interval` | A bounded time interval or slot from a registered granularity. |
| `set` | A bounded list or set at or below a registered maximum cardinality. |
| `object` | A structured result with enumerated fields, each itself bounded, subject to a registered maximum serialized size. |
| `attribute` | One selected attribute value released in full. |
| `ciphertext` | A value encrypted to a constrained recipient, readable only under a profile that constrains what code decrypts it. |

`ciphertext` is defined here for vocabulary stability. It has no v0.1 release path;
it exists for the attested-use profile.

---

## 5. Assurance profiles

An **assurance profile** describes *why the recipient should trust the result*.

| Identifier | Establishes | Status |
|---|---|---|
| `authenticated-answer` | The response originated from, and was not altered since leaving, the signing computation executor, and is bound to this request and receipt. | **v0.1. The default and minimum conforming profile.** |
| `credential-backed` | An issuer attested the underlying attribute; presentation is bound to this query. | Future. |
| `verifiable-computation` | A registered program produced this output from committed inputs and declared public context. | Future. |
| `attested-use` | Release occurred to a measured execution environment under a verified attestation and key-release policy. | Future. |

The same `boolean` release may carry any of these. They are different assurance
properties, not different disclosure sizes.

A responder MUST NOT silently downgrade a requested profile, and the response
identifies the profile actually used.

### 5.1 Signature suite

A **signature suite** names the signature algorithm, the serialization method
that produces the signed bytes, and the hash, as one identifier — because they
fail together. Carried in `signature.profile`, registered and versioned in
[`crypto-suites.md`](crypto-suites.md), and always a field of the *signed*
object rather than the outer envelope, so that an intermediary cannot rewrite it.

A suite is orthogonal to an assurance profile. The suite says how a signature was
produced; the assurance profile says what the signature means. `authenticated-answer`
under `eddsa-jws-2026` and under a future hybrid suite are the same assurance
property with different cryptographic strength.

Q2D is **algorithm-agile**: suites are added, deprecated, and withdrawn without a
protocol revision. Q2D is **not** post-quantum ready, and no 0.1 suite offers any
post-quantum property. See §9 for why that distinction is enforced.

### 5.2 Containment profile

The requester-side profile is versioned separately from assurance profiles and
identified as `q2d-contained-runtime-0.1`. It is a property of the *requester*,
not of the answer. See §7.

---

## 6. Policy and disclosure accounting

| Term | Definition |
|---|---|
| **Policy engine** | The component returning `allow`, `deny`, or `escalate` plus modifiers, given the authenticated request context. Q2D specifies its input and output contract, not its language. |
| **Decision modifier** | A narrowing attached to an `allow`: coarser shape, lower cardinality, stricter freshness, reduced sink set, or a required assurance profile. **A modifier coarsens; it never subsets** — the same rule that binds a requester, and for the same reason. It may not coarsen an `enum`: that coarsening is a mapping declared in an answer contract, which a modifier does not have ([`core-model.md`](core-model.md) §3.2). A requester either accepts the narrowed contract or abandons the task; it is never given a broader answer and asked to discard the excess. |
| **Effective answer domain** | The narrowing composition of the registry entry's canonical domain, the requester's answer contract, and any policy modifiers — not an intersection of their *values*, because coarsenings of different granularity do not intersect. Where two narrowings reach one dimension the composed value is their greatest lower bound, which for a range or a field set is the intersection of the **narrowing's parameter** and not of the domain. See [`core-model.md`](core-model.md) §3 and §3.3. **Computed by the responder.** A requester may request a *coarser* form of the registered domain; it can never expand it and never request a strict subset, and a requester-asserted domain is never trusted. See [`core-model.md`](core-model.md) §2.5 for why subsetting is prohibited. |
| **Sensitivity classification** | The registry- and policy-assigned class of a predicate, governing minimum assurance, normalization behaviour, and budget keying. Sensitivity is orthogonal to capacity: a one-bit answer can be maximally sensitive. |
| **Disclosure-capacity budget** | A policy-defined allowance debited on release, in proportion to `log2(cardinality(effective_answer_domain))`. A throttle and escalation trigger. **Never** described as a differential-privacy, inference, or posterior-risk guarantee. It measures the capacity of the answer alphabet, not what an adversary learned. |
| **Capacity debit** | The charge for one release, taken by the responder from the registry entry for the effective domain. Any debit asserted by a requester is ignored. |
| **Millibit** | The unit of capacity: one thousandth of a bit, carried as an integer. `ceil(1000 × log2(cardinality))`, authored once into a registry entry and never computed at runtime. Integer accumulation is exact and order-independent; ceiling rounding can over-charge but never under-charge. See [`core-model.md`](core-model.md) §3.1. |
| **Disclosure history** | The prior-release state consulted during policy evaluation and keyed by a policy-defined tuple such as (requester relationship, subject, sensitivity class, sink, time window). |
| **Denial normalization** | Mapping several internal outcomes — absent data, policy refusal, budget exhaustion, rate-limit rejection, unsupported predicate, failed freshness, internal escalation — onto one external class within a sensitivity class. Reduces explicit oracles. It is **not** wire-level indistinguishability: timing, size, notifications, rate limits, and later state remain observable. |
| **Explicit escalation** | An `escalate` response returning an opaque pending token. This reveals that a relationship, record, or applicable policy path may exist, and is therefore itself a disclosure requiring its own policy decision. It MUST NOT be described as denial-normalized. |
| **Opaque escalation** | Internal escalation recorded and prompted out of band while the external response stays in the normalized class. The original query remains idempotent: identical retries keep returning the cached normalized outcome and never become an answer. |
| **Approval-scope digest** | The key of a time-bounded grant recorded on approval under opaque escalation. Covers requester principal and delegated agent, predicate and version, answer-contract digest, purpose, answer recipient, sink set, and public-context commitment. Excludes query identifier, nonce, issue time, and expiry — so a fresh signed query can carry the same scope. The grant it keys is **single-use** — consumed by the first release made under it, so one approval authorizes one answer ([`core-model.md`](core-model.md) §5.3). Exact field list is open; see §10. |
| **Residual oracle** | An observable channel Q2D reduces but does not close. Named, not hidden. The unavailable-to-answer transition after an opaque approval is one. |

---

## 7. Requester-side containment

| Term | Definition |
|---|---|
| **Sink** | Any destination that may receive the answer or a derivative: a remote model endpoint, a tool, an API, a person, a log, a trace, agent memory, a database, a file, a queue, a network endpoint, a debugging console, analytics. **A remote model provider is a sink.** A deployment sending an answer to a hosted model has not kept it on-device. |
| **Model context** | The material visible to a language model. Signatures, credentials, proofs, policy traces, receipts, and private inputs are kept out of it; the semantic answer alone crosses in, unless local policy permits more. |
| **Evidence segregation** | Verifying signatures, credentials, proofs, and receipts in the requester runtime and passing only the semantic answer to the agent. |
| **Label** | Confidentiality, integrity, provenance, purpose, sink, and retention metadata attached to an answer and conservatively inherited by derived values absent an explicit declassification rule. |
| **Mediation** | Interposing on a sink so a labelled value cannot reach it unauthorized. The containment property is conditional on *complete* mediation and fails for any unmediated path. |
| **Compatibility mode** | An ordinary MCP or A2A client using Q2D source-side queries without containment enforcement. Such a deployment may claim a bounded authenticated answer from a participating custodian. It may **not** claim that answer-derived flow is restricted to permitted sinks. |

---

## 8. Scope terms

| Term | Definition |
|---|---|
| **Participating custodian** | A custodian whose runtime is authorized to evaluate the query and release the answer. **Q2D 0.1 applies only to participating custodians.** |
| **Subject-mediated policy** | A deployment pattern in which a data subject's preference or approval is one recognized policy authority. A supported pattern — not an assumption that a subject can impose policy on an arbitrary third-party silo. |
| **Least disclosure** | Disclosure bounded by a registered predicate, an answer contract, and policy. Not a claim that a bounded answer is harmless, and not a claim of global minimality. |

---

## 9. Controlled claim language

The left column is the project's vocabulary. The right column is prohibited in the
report, the specification, the repository, the site, and any public
communication — each overstates a guarantee Q2D does not have.

| Use | Do not use | Because |
|---|---|---|
| authenticated answer | cryptographically proven answer | A signature proves origin and integrity, not correct computation, correct source selection, or input truth. |
| disclosure-capacity budget | leakage budget, privacy budget | Capacity of an answer alphabet is not a measure of what an adversary learned. |
| denial normalization | wire-level indistinguishability | Timing, size, notification, rate-limit, and state channels remain. |
| attested-use release | tamper-proof courier, guaranteed destruction | Attestation constrains which code decrypts; it does not follow plaintext after legitimate egress. |
| GDPR technical-control mapping | compliance-by-construction | Controller roles and lawful basis depend on actual processing activities, not protocol labels. |
| supports data-minimization objectives | GDPR-compliant, privacy-guaranteed | The protocol supplies controls and evidence; it does not determine compliance. |
| answer recipient / permitted sinks | the data never leaves your device | Untrue whenever a remote model endpoint or external sink is in the path. |
| bounded answer | one bit, therefore harmless | Capacity is not severity. |
| predicate registry entry | schema | A registry entry carries domain, capacity, sensitivity, and provenance, not only a shape. |
| participating custodian | data owner, data holder | Neither term distinguishes operation of a source from authority over its release. |
| algorithm-agile; a suite registry that can carry post-quantum or hybrid suites | post-quantum ready, quantum-resistant | No registered 0.1 suite offers any post-quantum property. Agility is the ability to add one, not the presence of one. |
| data subject *or* policy authority, chosen deliberately | the two used interchangeably | The conflation is the specific error the v0.1 role model exists to correct. |

Claims that Q2D is "the first" anything require an exhaustive literature and
patent search that has not been performed. Until then: "a protocol architecture
combining…".

---

## 10. Terms deliberately not defined in 0.1

Naming these prevents their informal use. Each requires its own specification
work before it enters the vocabulary.

Registry federation, cross-signing, and conflict resolution · multi-subject policy
reconciliation · free-form natural-language predicates · general verifiable
computation · public transparency logs · destruction receipts · sticky policy ·
conformance mark · formal inference privacy · certification program.

Open items carried from Appendix C of the technical report that bear on this
vocabulary: the exact approval-scope digest fields and grant lifetime; the
capacity calculation for bounded structured outputs; and which identity profile,
if any, is mandatory to implement.

Decided since that appendix was written, and no longer open: the
core-versus-profile boundary for identity and delegation
([`core-model.md`](core-model.md) §2.3 defines the three interfaces); grant
multiplicity (single-use, §5.3); and **whether denied and escalated outcomes debit
the budget** — they do not, and a required rate limit bounds the probing instead
(§9.1).

Appendix C's *canonical serialization and signature container* is no longer
open. Signed bytes are the exact transmitted bytes
([`core-model.md`](core-model.md) §2.1) and algorithms are named by suite
([`crypto-suites.md`](crypto-suites.md)), so canonicalization is not on the
security path.

---

## 11. Change control

A term's identifier is stable once an implementation depends on it. Release-shape
and assurance-profile identifiers (§4, §5) are the identifiers most likely to
appear on the wire and in registry entries; changing one is a breaking protocol
change, not an editorial change.

Additions to §9 are expected as new overstatements are caught in review.
