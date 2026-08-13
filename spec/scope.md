# Q2D Scope — version 0.1

**Protocol version:** 0.1 (pre-release)
**Document status:** Specification spine — working draft, not yet a normative specification.

This document states what Q2D 0.1 covers, what it defers, and what it will not
cover at any version. Its purpose is to keep the protocol small enough to
specify, implement, and attack before it grows.

Terms are defined in [`terminology.md`](terminology.md). Claims about what the
in-scope protocol achieves are in [`claims.md`](claims.md).

Where this document and the technical report disagree, this document governs.

---

## 1. The version 0.1 boundary

> Q2D 0.1 covers queries over data held by a **participating custodian** whose
> runtime is authorized to evaluate the query and release the answer.

Everything else follows from that sentence. It is the narrowest scope in which
the protocol's claims are defensible, and it was chosen deliberately over the
more appealing framing — that a person's agent governs information about them
wherever it lives — because the appealing framing is not something the
architecture can deliver.

A data subject cannot unilaterally impose policy on a silo they do not operate.
For subject preference to have effect, the custodian must recognize the subject,
resolve which policies apply, consult the subject or a standing rule, and agree
to enforce the outcome. That is a participating custodian. Where the custodian
does not participate, Q2D has nothing to say.

Subject-mediated policy is therefore a **supported deployment pattern**, not an
assumption the protocol makes about the world.

## 2. What a participating custodian must be able to do

A deployment is in scope only if the custodian can:

1. authenticate a requester principal and verify delegation to a requester agent;
2. resolve a predicate identifier and version against a registry it trusts, and
   reject anything it does not recognize;
3. determine which policy authorities apply to the source, and obtain a decision
   from them;
4. evaluate the registered predicate locally over private input, without
   releasing that input through the Q2D interface;
5. validate the result against the effective answer domain before release;
6. maintain the disclosure state its policy keys on;
7. sign a response and issue a receipt under an identity the requester can
   verify.

A deployment that cannot do all seven is not a conforming Q2D responder. It may
still be a useful predicate API; it is not this protocol.

## 3. Deployment patterns in scope

| Pattern | Custodian | Policy authority | Subject |
|---|---|---|---|
| **Personal agent or vault** | the person's own device or hosted store | the same person | the same person |
| **Enterprise data gateway** | the company | the company | an employee, customer, or no identified person |
| **Cross-organization exchange** | the responding organization | the responding organization, possibly under contract | varies |
| **Credential-backed decision** | the holder or an evaluating custodian | custodian, possibly bound by issuer restrictions | the credential subject |

Roles collapse differently in each. The specification never assumes a
particular collapse.

## 4. Predicate scope

Q2D 0.1 evaluates **registered, versioned, bounded** predicates only.

In scope: a predicate with an input schema, a public-context schema, an output
schema, a canonical answer domain, a capacity calculation, a sensitivity
classification, and deterministic test vectors — published in a registry the
custodian pins.

Out of scope for 0.1: free-form natural-language questions, requester-supplied
expressions, and arbitrary code. A requester selects from what the custodian's
registry offers. It may request a **coarser form** of a registered domain; it
may never expand one, and it may never request a strict subset. See
[`core-model.md`](core-model.md) §2.5 for why subsetting is prohibited.

### 4.1 The schema profile a registry entry may use

An entry's schemas are JSON Schema, and **only this subset of it**:

`$schema` · `type` · `required` · `properties` · `additionalProperties: false` ·
`enum` · `items` · `minItems` / `maxItems` · `minLength` / `maxLength` ·
`minimum` / `maximum` · `format: date-time`

**`format: date-time` asserts.** In JSON Schema 2020-12 `format` is an
annotation unless the Format-Assertion vocabulary is in force, so a validator
may accept any string for it — which would make request validity depend on which
library a responder chose, the divergence this profile exists to prevent, hiding
inside the profile. Here it is a constraint, and the value it constrains is
[`core-model.md`](core-model.md) §2.2's timestamp: uppercase `T`, uppercase `Z`,
second precision. A validator implementing this profile checks that form rather
than deferring to a library's idea of a date.

The rule binds the value validated against the schema, **however it travelled**.
§2.4 lets public context arrive inline in the signed core object or as a digest
with the value carried separately; in the first case §2.2 reaches it directly,
and in the second `predicate.public_context_digest` — which is in the signed
object — commits to the value's bytes, so a different spelling produces a
different digest and the separately-carried value no longer matches what was
signed. (Not the *entry* digest, which §2.4.1 defines over the registry entry
and which says nothing about a request's values.) Either way one spelling is the
only one that works.

`$schema` is required and declares the dialect —
`https://json-schema.org/draft/2020-12/schema` for 0.1. It is a declaration
rather than an assertion, and it is in the profile because two implementations
validating against different dialects is the divergence this profile exists to
prevent, arrived at one level up.

**Nothing else.** No `$ref`, no `oneOf` / `anyOf` / `allOf` / `not`, no
`patternProperties`, no regular expressions, no remote schema resolution.

Three rules about how the profile is used, not only which keywords it contains:

- **Every object schema sets `additionalProperties: false`** — every one, not
  only the outermost. An object that omits it accepts fields the entry never
  declared, which is unvalidated input reaching a predicate, and a nested object
  is where that is easiest to miss.
- **`$schema` appears once, at the root.** JSON Schema lets a nested `$schema`
  switch dialects for that subschema, which would reintroduce the divergence
  pinning the dialect prevents, one level down.
- **A schema is an object.** JSON Schema permits `true` and `false` as
  subschemas, accepting or denying everything with no keyword to check; a
  profile that is a list of keywords does not admit a schema that has none.

The reason is not economy. **Two JSON Schema libraries disagree on edge cases**,
and a disagreement here is a disagreement about whether a request is valid at
all — one responder accepting what another rejects, with neither wrong by the
library it uses. Restricting the language is cheaper than reconciling two
implementations of all of it. Remote resolution and unbounded regular
expressions are refused for a second reason: a `$ref` to a URL is a network
fetch during validation, and an unbounded expression is a denial-of-service
surface, both on input that is authenticated by then ([`core-model.md`](core-model.md)
§4 step 11 follows step 4) but still hostile.

**The list is frozen, and extending it is a change to this document.** A
predicate whose public context needs `oneOf` is complicated enough that its
schema is not where the complexity should be resolved — which is the same
judgement §4 already makes in putting requester-supplied expressions out of
scope.

The Phase 1 registry is deliberately minimal — a signed manifest distributed
with the application, whose signing key and digest the custodian pins locally.
The reference manifest begins with three predicates: `menu_compatible`,
`availability_window`, and `contactable_for`.

## 5. Assurance scope

Version 0.1 defines one conforming assurance profile: `authenticated-answer`.

`credential-backed`, `verifiable-computation`, and `attested-use` are named in
[`terminology.md`](terminology.md) §5 so the vocabulary is stable, and are
specified separately. They are **not** rungs of a ladder above the Phase 1
profile; they answer different questions and carry different trust assumptions.
An implementation claiming one of them inherits none of Phase 1's security
review.

## 6. Transport scope

The core exchange is transport-neutral. A binding maps it onto MCP, A2A, or
direct HTTPS without changing the meaning of an answer contract.

Bindings are separate specifications. A binding is in scope for 0.1 only to the
extent that it preserves principal and delegation identity, the predicate and
registry reference, the answer contract, purpose and delivery constraints,
freshness and replay semantics, response status, evidence and receipt binding,
and idempotency behaviour. A binding that silently broadens an answer domain or
drops a sink because its transport lacks a field for it is non-conforming.

## 7. Deferred — later versions or separate profiles

Each of these is a real requirement that 0.1 does not meet. They are deferred
because specifying them now would either be guesswork or would delay the parts
that can be implemented and attacked today.

| Deferred | Why | Where it goes |
|---|---|---|
| Subject control over data in a **non-participating** silo | Requires custodian integration and secure record-to-subject binding that does not exist | Later profile |
| **Multi-subject** records with conflicting policies | One person's denial can reveal another's participation; no sound default exists yet | Later version; 0.1 fails closed |
| Registry **federation**, cross-signing, precedence | Needs implementation experience before standardizing | Later version; 0.1 uses one pinned registry |
| **Free-form** or natural-language predicates | No way to bound an answer domain that was not registered | Possibly never in the core |
| **Verifiable computation** and zero-knowledge predicate proofs | Requires program registry, input commitments, and cryptographic review | `verifiable-computation` profile |
| **Attested-use** release to downstream services | Inherits hardware, attestation, and side-channel assumptions | `attested-use` profile |
| **Public transparency logs** | Public disclosure histories create correlation and dictionary-attack risk | Later profile, separately analysed |
| **Posterior-risk** or differential-privacy accounting | 0.1 charges answer-alphabet capacity, which is materially weaker | Later profile |
| Formal **timing and padding** normalization | Needs a defined indistinguishability property and its tests | Later profile |

Deferral is not endorsement of the 0.1 behaviour as sufficient. Where a
deployment's threat model requires a deferred capability, Q2D 0.1 is the wrong
tool.

## 8. Permanently out of scope

These will not enter the protocol at any version, because no protocol can
deliver them. They are listed so that no future version quietly claims them.

- **Retracting a released answer.** A recipient who has learned a fact has
  learned it. Revocation governs future requests only.
- **Proving self-asserted input true.** A signature over "I am vegetarian"
  authenticates the assertion, not the fact.
- **Proving declared purpose honest.** A signed purpose is attributable
  evidence, not evidence of intent.
- **Controlling a human recipient.** Q2D governs machine flows.
- **Determining legal compliance.** The protocol supplies controls and
  evidence; controller roles and lawful basis depend on actual processing.
- **Enforcing policy in arbitrary external systems** once plaintext has
  legitimately left a controlled runtime.

## 9. Changing scope

An addition to scope requires: a stated threat it addresses, the claim it would
support, the assumptions that claim rests on, and a test that fails when the
mechanism is absent. Scope grows by specification, not by implementation.

Reductions in scope are recorded here rather than silently dropped, so that a
reader of an earlier draft can tell what changed.
