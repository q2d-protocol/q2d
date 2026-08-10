# Q2D Phase 1 MVP — scope and plan

**Status:** planning document. Supersedes nothing normative.
**Target:** a Q2D exchange somebody outside this project can stand up and attack.

This document defines what Phase 1 builds, in what order, and how the work is
decomposed. It is the parent of the PRD set; each stage below becomes one or
more PRDs, each PRD enumerates issues, each issue is tracked.

---

## 1. Definition of done

MVP is reached when a person who has never seen this repository can, from public
artifacts alone:

1. run a **custodian** on one machine and a **requester** on another;
2. pair them under the local pairing profile;
3. have the requester ask `menu_compatible` and receive a bounded, signed answer
   with a receipt it can verify;
4. observe a **denial** and a **normalized denial** and be unable to distinguish
   causes on the wire;
5. exhaust a disclosure-capacity budget and watch the next query escalate;
6. run the **conformance harness** against both implementations and see them
   agree;
7. swap them — the **Rust requester against the Go custodian and vice versa** —
   and see identical behaviour.

Item 7 is the one that matters. Anything less than cross-implementation
interoperability is one implementation with a spare copy.

### MVP completion is not Phase 1 completion

The list above is the walkthrough. It is **not** the condition
[`spec/claims.md`](../spec/claims.md) sets for describing Phase 1 as complete,
which is that every claim maps to at least one passing executable check.

At the end of MVP, three of the thirteen claims will still have no passing test:

| Claim | Why |
|---|---|
| Q2D-C-11 binding equivalence | Equivalence is a statement between two bindings. MVP builds one |
| Q2D-C-12 evidence segregation | Conditional on `q2d-contained-runtime-0.1`; CC-10 is not built |
| Q2D-C-13 conditional flow confinement | Same |

They are design intentions with no passing test, and
[P-016](prds/P-016-demonstration-adversarial.md) §4.6's traceability matrix
reports them that way — in the same table as the ten that pass, rather than
omitted or footnoted.

**No artifact may describe finishing this walkthrough as completing Phase 1.**
The two documents use "done" for different things, and only one of them is read
by people deciding whether to trust the protocol.

### What "attackable" means concretely

The published artifacts must let someone attempt, without our help: answer-domain
understatement, capacity-debit forgery, suite downgrade, replay, duplicate debit,
purpose substitution, sink substitution, registry-digest substitution, adaptive
probing to reconstruct a constraint set, and timing analysis of denial paths.
Every one of those has a claim it would break in
[`spec/claims.md`](../spec/claims.md).

---

## 2. Explicitly not in MVP

Deferring these is what makes MVP finishable. Each is deferred in
[`spec/scope.md`](../spec/scope.md) §7 or by conformance class.

| Not building | Why | Class |
|---|---|---|
| Contained requester runtime | Large, and the source-side claims stand without it | CC-10 |
| MCP binding | HTTPS is the reference binding; MCP follows once semantics are proven | CC-8 |
| A2A binding | Same | CC-9 |
| Credential, verifiable-computation, attested-use profiles | Deferred by scope; each needs separate cryptographic review | CC-5/6/7 |
| Store-and-forward relay, HPKE payload protection | Needs the relay profile, which 0.1 does not specify | — |
| Registry federation | Needs implementation experience first | — |
| Multi-subject policy reconciliation | No sound default exists; 0.1 fails closed | — |
| Write predicates | Read-only surface only | — |

**Compatibility mode is the MVP posture.** A deployment built to this plan may
claim *"bounded authenticated answer from a participating custodian."* It may not
claim *"answer-derived flow restricted to permitted sinks."*

---

## 3. How the documents relate

The single most important rule in this plan:

> **The specification says what must be true. A PRD says how we build and verify
> it. A PRD cites a requirement; it never restates one.**

A PRD that paraphrases `spec/` creates a second source of truth that can drift.
Where a PRD author finds the spec ambiguous or wrong, that is a **spec bug** —
fix `spec/`, then cite the fix. Resolving it inside a PRD is how two
implementations end up disagreeing while both "pass their PRD."

| Layer | Owns | Changes when |
|---|---|---|
| `spec/`, `threat-model/` | what must be true; claims; conformance classes | the protocol changes |
| `registry/` | predicate definitions, domains, capacities, vectors | a predicate is added or revised |
| `docs/mvp-scope.md` (this) | stage order, decomposition, gates | the plan changes |
| PRDs | module boundaries, interfaces, test strategy, acceptance | the build approach changes |
| Issues | one unit of work with a definition of done | continuously |
| `CONVENTIONS-{rust,go}.md` | idiom: error types, async, layout, tooling | rarely |

### One PRD set, not two

PRDs are **language-neutral**. Every acceptance criterion is stated as *"both
implementations pass corpus section X."* Language-specific decisions live in one
conventions document per language, not duplicated per PRD.

Two PRD sets would let the implementations diverge in design while each passed
its own document. The point of building two is that they are built from one
description and checked against one corpus.

---

## 4. Stages

Stages are strictly ordered by dependency. Each has an exit gate that must pass
in **both** languages before the next begins.

### Stage 0 — Shared conformance corpus and harness

**Before any implementation code.** The corpus is the contract; building it last
means discovering divergence last.

- Vector format and a language-agnostic runner contract: each implementation
  ships a CLI that reads a vector file and emits a result file; the harness
  diffs against expectations.
- Message vectors: known keys, known payloads, known-good signatures.
- Processing-order vectors: which step rejects which malformed request.
- Budget vectors: debit sequences and running totals in millibits.
- Receipt vectors: field binding and digest computation.
- The existing [`registry/`](../registry/) vectors plug in as the
  predicate-validation section.

**Gate:** the harness runs, reports pass/fail per vector, and currently fails
everything because no implementation exists. A harness that cannot fail is not a
harness.

**Size:** M · **Risk:** low · **Blocks:** everything

---

### Stage 1 — Message layer and cryptographic suites

Envelope, signing, verification, replay primitives. No policy, no predicates, no
registry.

- Envelope: opaque `signed` object plus advisory `routing` projection
  ([`core-model.md`](../spec/core-model.md) §2.1), including the rule that
  `routing` is a strict subset and any disagreement rejects.
- `eddsa-jws-2026`: sign exact bytes, verify before parse.
- Suite resolution, verifier minimum-acceptable policy, downgrade rejection
  ([`crypto-suites.md`](../spec/crypto-suites.md) §4).
- Key generation and storage for test purposes only.
- Nonce, expiry, clock-skew, replay cache.

**Gate:** **cross-verification.** The Rust implementation verifies signatures
produced by Go and vice versa, over the Stage 0 message vectors. A downgrade
attempt is rejected by both. This gate is the earliest point at which the
two-implementation claim becomes real.

**Claims:** Q2D-C-05, Q2D-C-07 · **Size:** L · **Risk:** medium

---

### Stage 2 — Registry client and request validation

- Manifest loading, signing-key pinning, digest pinning, fail-closed on
  unknown predicate, unknown version, or unpinned digest.
- Public-context schema validation against the registry entry's schema.
- Answer-contract narrowing check: requester may request a coarser form, never
  an expansion and never a strict subset
  ([`core-model.md`](../spec/core-model.md) §2.5).
- Effective answer domain as the narrowing composition of registry, contract, and
  policy modifiers — not a set intersection
  ([`core-model.md`](../spec/core-model.md) §3).
- Capacity lookup — **read from the entry, never computed**
  ([`core-model.md`](../spec/core-model.md) §3.1).

**Gate:** every [`registry/`](../registry/) vector passes in both; domain
understatement and expansion are both rejected; a manifest with a wrong digest is
refused before any private access.

**Claims:** Q2D-C-02 · **Size:** M · **Risk:** low

---

### Stage 3 — Policy engine, budget, denial normalization

- Policy input/output contract; `allow` / `deny` / `escalate` plus modifiers.
- Fail-closed invariants as **property tests**, not examples: unknown scope,
  missing mandatory authority, conflicting authorities, unresolvable context.
- Restrictive composition across multiple authorities.
- Budget store keyed by a policy-defined tuple; integer millibit accumulation;
  debit-once idempotency. **Only a released answer debits** — a denial, an
  escalation, and a rate-limit rejection do not
  ([`core-model.md`](../spec/core-model.md) §9.1).
- Rate limiting at [`core-model.md`](../spec/core-model.md) §4 **step 9a**, keyed
  on the **relationship only** — not the full budget key, because sensitivity
  class is not known until step 10, and a limiter that skipped unresolved
  predicates would leave unknown ones unlimited and become an existence oracle.
  **Required configuration with no default**; the responder refuses to start
  without it, and a rate-limit rejection is normalized like any other cause.
- Denial normalization: one external class per sensitivity class, identical
  payload, identical size, identical retry semantics.

**Gate:** a property test asserts no user-authored rule can override a
fail-closed invariant. A test asserts that every rejection cause in a normalized
class produces a byte-identical response — the same cross-vector invariant
`registry/validate.py` already applies to registry rejections.

**Claims:** Q2D-C-08, Q2D-C-09 · **Size:** L · **Risk:** medium

---

### Stage 4 — Responder pipeline, predicates, receipts

Where the previous stages become a responder.

- The [`core-model.md`](../spec/core-model.md) §4 processing order, steps 1–19,
  in order, with the ordering itself asserted by test.
- The three registry predicates evaluated locally.
- Output validation against the effective domain; fail-closed on violation; no
  private input in any error path.
- Receipt construction and signing; local audit event distinct from and larger
  than the receipt.

**Gate:** an ordering test proves no private input is read before step 16. An
error-path test proves no private value reaches a serialized error. Receipt
digests match Stage 0 vectors.

**Claims:** Q2D-C-03, Q2D-C-04, Q2D-C-06, Q2D-C-10 · **Size:** L · **Risk:** medium

---

### Stage 5 — Requester runtime

- Query construction and signing; answer-contract derivation.
- Response verification **before** the answer is exposed to a caller, in the
  order [`core-model.md`](../spec/core-model.md) §4.1 makes normative.
- Receipt storage and verification.
- Semantic-answer projection: the caller receives the answer, not the evidence.

**Gate:** a requester rejects a response whose suite is below its floor, whose
signature fails, or whose receipt does not bind the request it sent.

**Claims:** Q2D-C-01. **Not Q2D-C-12** — it is conditional on
`q2d-contained-runtime-0.1`, CC-10's honesty rule forbids claiming containment
for a path that is not mediated, and this stage mediates no sinks. The
verification boundary it does build is a design intention with no passing test
([P-012](prds/P-012-requester-runtime.md) §4.8). "Partial" is not a state
[`spec/claims.md`](../spec/claims.md) defines.
· **Size:** M · **Risk:** low

---

### Stage 6 — Direct HTTPS binding and runnable daemon

- `POST /.well-known/q2d/query`, `GET /capabilities`, `GET /pending/{token}`.
  **No `GET /predicates/{id}/{version}`** — it answers "does this custodian
  support this predicate?" with a status code, which is the existence oracle
  [P-005](prds/P-005-registry-client.md) §4.7 spends nine uniform failure paths
  closing, and it makes [`../spec/core-model.md`](../spec/core-model.md) §2.4.1's
  entry-digest check vacuous by handing the requester the entry it is meant to
  have obtained independently. Registry distribution stays out of band. If
  discovery is ever needed, the shape is authenticated and policy-gated.
- A custodian daemon someone can actually run, with configuration for pinned
  registry, keys, and policy.
- Identity: **local pairing profile only** — the smallest of the three profiles.

**Gate:** the definition-of-done walkthrough in §1 completes on two machines,
executed by following the published quickstart and nothing else.

**Claims:** none. Q2D-C-11 is a statement *between* bindings and this stage
builds one, so it is not attributable here — a qualifier in this cell would not
survive being copied into a coverage table.
**Conformance:** CC-12, the direct HTTPS binding class
([`../spec/conformance-classes.md`](../spec/conformance-classes.md)). Class
conformance and claim coverage are different things and are stated in different
fields for that reason.
· **Size:** L · **Risk:** medium

---

### Stage 7 — Escalation lifecycle

Last MVP item. The consent path is central to the value proposition but not to
standing the system up.

- Explicit escalation: pending token, status polling, and a receipt on the
  `escalate` response ([`core-model.md`](../spec/core-model.md) §5.3).
- Opaque escalation: normalized outcome — response *and* receipt — out-of-band
  prompt, approval-scope digest, time-bounded **single-use** grant, fresh-query
  revalidation.
- Idempotency: an identical retry never becomes an answer after approval.

**Gate:** a test asserts that replaying the original query after approval returns
the cached normalized outcome; that a fresh query with a matching approval-scope
digest is revalidated end to end rather than served from the grant; and that a
*second* fresh query under the same grant escalates again rather than answering.

**Claims:** Q2D-C-07 (extended) · **Size:** M · **Risk:** **high** — this is the
most intricate semantics in the protocol, and while several of its Appendix C
items are now decided ([`core-model.md`](../spec/core-model.md) §9), the
approval-scope field list and grant lifetime remain open

---

### Stage 8 — Reproducible demonstration

- Two-party scenario with synthetic data, scripted and deterministic.
- The adversarial suite: probing, replay, understatement, substitution, timing.
- Disclosure measurement, reporting source bytes, model-context bytes, and total
  wire bytes **separately**.
- Quickstart, deployment, and operational-security documentation.

**Gate:** an outsider reproduces the demo and the measurements from the published
artifacts.

**Size:** M · **Risk:** low

---

## 5. PRD set

Sixteen PRDs. Numbers are permanent once assigned; a PRD that is abandoned keeps
its number and is marked withdrawn.

| # | PRD | Stage | Size |
|---|---|---|---|
| P-001 | Conformance corpus format and harness contract | 0 | M |
| P-002 | Message envelope and canonical structures | 1 | M |
| P-003 | Cryptographic suites, key handling, downgrade policy | 1 | M |
| P-004 | Replay, expiry, idempotency | 1 | S |
| P-005 | Registry client: pinning, resolution, fail-closed | 2 | M |
| P-006 | Request validation and effective answer domain | 2 | M |
| P-007 | Policy engine contract and fail-closed invariants | 3 | L |
| P-008 | Disclosure-capacity accounting | 3 | M |
| P-009 | Denial normalization | 3 | M |
| P-010 | Responder pipeline, predicate execution, output validation | 4 | L |
| P-011 | Receipts and local audit | 4 | M |
| P-012 | Requester runtime | 5 | M |
| P-013 | Direct HTTPS binding and custodian daemon | 6 | L |
| P-014 | Identity and the local pairing profile | 6 | M |
| P-015 | Escalation lifecycle | 7 | M |
| P-016 | Reference demonstration and adversarial suite | 8 | M |

Sixteen, where the first cut of this plan said twelve — the count grew while
enumerating gates, which is itself information: Stages 1, 3, and 4 each carry
more than one separable concern.

### What every PRD must contain

1. **Purpose** — one paragraph, and the claim(s) it serves.
2. **Spec citations** — the exact requirements it implements, by identifier.
   Never a paraphrase.
3. **Module boundary** — what is inside, what is explicitly not.
4. **Interfaces** — language-neutral signatures; the contract both
   implementations honour.
5. **Corpus sections** — which vectors exercise it, and which are new work.
6. **Acceptance** — stated as "both implementations pass X", never as prose.
7. **Negative acceptance** — what must fail, and how that failure is observed.
8. **Escalate-if-changed decisions** — choices that are architecture, not
   preference, flagged so a later contributor stops rather than pivots.
9. **Open questions** — with the spec item they belong to, if any.
10. **Issue list** — the decomposition into tracked work.

Items 7 and 8 are borrowed directly from the Deeta PRD format, which uses both to
good effect. Item 7 matters most here: for a protocol whose value is what it
refuses, a PRD without negative acceptance is untestable.

---

## 6. Language split

| Shared — one source | Per-language |
|---|---|
| PRDs | `CONVENTIONS-rust.md`, `CONVENTIONS-go.md` |
| Conformance corpus | Error type idiom |
| Registry manifest | Async model and concurrency |
| Interface contracts | Module and package layout |
| Acceptance criteria | Test framework and fixtures |
| Spec and threat model | Dependency policy |

Each conventions document is written **once, at Stage 1**, and revised rarely. If
a PRD needs a language-specific decision, that is a signal the decision belongs in
the conventions document instead.

### Honesty about independence

Both implementations will be written by the same author. That demonstrates the
specification is *implementable* — which is the real purpose — but it does not
make either implementation *independent* in the standards sense. Describe them as
"two implementations", never "an independent implementation", until someone
unaffiliated builds a third.

The discipline that makes two worth having is the shared corpus. Every divergence
it catches is a specification ambiguity found before an outsider finds it.

---

## 7. Risks

| Risk | Consequence | Mitigation |
|---|---|---|
| The corpus is written to match the first implementation | The second implementation is a port, and the corpus proves nothing | Stage 0 precedes all code. Vectors are derived from `spec/`, and every vector cites the requirement it exercises |
| Escalation semantics prove underspecified | Stage 7 stalls | Appendix C items are already open. Expect spec changes; budget for them rather than working around them |
| A PRD silently resolves a spec ambiguity | Implementations diverge while both pass their PRDs | Spec-citation rule; ambiguity is escalated to `spec/`, not decided locally |
| Policy engine scope creep | Q2D reinvents a policy language it explicitly declined to build | The engine's contract is input/output only. A rule syntax richer than the MVP needs is out of scope |
| Timing side channels ignored until late | A claim about denial normalization that testing does not support | Timing measurement is in Stage 8's adversarial suite, and `Q2D-NC-05` already scopes the claim honestly |

---

## 8. Pipeline

```
docs/mvp-scope.md   (this)      what and in what order
        ↓
PRD P-0xx           per module   how it is built and verified
        ↓
Issues                           one unit of work, one definition of done
        ↓
Issue tracker                    execution
```

A PRD is finalized when every section in §5 is complete and its issue list is
enumerated. An issue is ready when it names its PRD, its acceptance, and the
corpus section that proves it.

**Next artifact: P-001.** The corpus format is the dependency for everything
else, and writing it will test whether the spec is precise enough to generate
vectors from — which is the cheapest possible review of the spec spine.
