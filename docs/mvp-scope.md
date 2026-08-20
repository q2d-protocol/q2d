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

1. stand up a **custodian as an MCP server** from a pinned predicate manifest;
2. configure a requester key and ask `menu_compatible`, receiving a bounded,
   signed answer with a receipt it can verify;
3. see the tool's `outputSchema` **come from the pinned registry entry**, and a
   value outside it never leave the server;
4. run an **injected payload** through the custodian's own data and watch it fail
   to reach the caller — then see the same payload succeed against a plain MCP
   tool over the same data;
5. observe a **refusal** and be unable to distinguish its cause from any other
   **in the same normalized class** — Tier A's informative values stay distinct
   on purpose ([`core-model.md`](../spec/core-model.md) §5.2.1);
6. run the **conformance harness** against both implementations and see them
   agree;
7. swap them — the **Rust responder against the Go one and vice versa** — and see
   identical behaviour.

Items 4 and 7 are the ones that matter. Item 4 is the demonstration: it is the
difference between a design argument and something a skeptic can run. Item 7 is
the evidence the specification is unambiguous — anything less than
cross-implementation agreement is one implementation with a spare copy.

**This list changed on 2026-08-19.** It previously required a two-machine pairing
ceremony, a bespoke HTTPS daemon, and exhausting a disclosure-capacity budget to
watch a query escalate. The pairing profile, the daemon and the budget are all
deferred (§2), and the walkthrough is the one the reduced scope can actually
complete.

### MVP completion is not Phase 1 completion

The list above is the walkthrough. It is **not** the condition
[`spec/claims.md`](../spec/claims.md) sets for describing Phase 1 as complete,
which is that every claim maps to at least one passing executable check.

At the end of MVP, **five of the thirteen claims** will have no passing test:

| Claim | Why |
|---|---|
| Q2D-C-09 disclosure-capacity accounting | **Deferred 2026-08-19.** A request quota bounds probing instead; the budget measured a quantity `claims.md`'s own *Fails if* list conceded was defeated by collusion, correlated predicates and cross-custodian spreading |
| Q2D-C-11 binding equivalence | Equivalence is a statement between two bindings. MVP builds one |
| Q2D-C-12 evidence segregation | Conditional on `q2d-contained-runtime-0.1`; CC-10 is not built |
| Q2D-C-13 conditional flow confinement | Same |
| Q2D-C-07 replay resistance *(partially)* | Holds for the responder's half; the requester-side entropy obligation has no responder-side check — [E-49](open-escalations.md) |

**[`claims.md`](../spec/claims.md) now carries this**, as of the same branch that
restaged this document. Each deferred claim is marked *not attempted in this
release* rather than deleted — stronger, and honest about what the demonstration
shows — and **Q2D-C-10's receipt field list has lost its capacity-debit entry**,
because a field whose only available value is zero is a lie in waiting.

This paragraph said the opposite until it was caught by review: it was written
while `claims.md` was deliberately untouched, and went stale inside its own
branch when the claims work landed two commits later. **The table above is the
record, not the plan.**

They are design intentions with no passing test, and
[P-016](prds/P-016-demonstration-adversarial.md)'s coverage reporting shows them
that way — in the same table as the ones that pass, rather than omitted or
footnoted.

**No artifact may describe finishing this walkthrough as completing Phase 1.**
The two documents use "done" for different things, and only one of them is read
by people deciding whether to trust the protocol.

### What "attackable" means concretely

The published artifacts must let someone attempt, without our help: **injection
through the custodian's own data**, **injection through `public_context`**, **an
out-of-domain value from a compromised predicate**, answer-domain understatement,
suite downgrade, replay, **duplicate evaluation on retry**, purpose substitution,
sink substitution, and registry-digest substitution. (*Duplicate debit* until
2026-08-20 — the budget is deferred, and what a retry must not do is evaluate
again.) Every one has a claim it would
break in [`spec/claims.md`](../spec/claims.md).

**The first three are new, and they are the headline.** Tool poisoning works
because an ordinary tool's response channel is wide enough to carry an
instruction. A Q2D predicate returns a boolean, a small enum, or a slot, and
[`core-model.md`](../spec/core-model.md) §4 step 17 validates before release —
so a payload in the data has nowhere to ride out. The third vector is the one
that makes it structural rather than incidental: it rigs the predicate itself to
return the payload and shows step 17 refusing anyway.

**Two attacks left this list**: adaptive probing to reconstruct a constraint set,
which attacked the deferred budget, and timing analysis of denial paths, which
[`claims.md`](../spec/claims.md) Q2D-NC-05 already concedes succeeds.

---

## 2. Explicitly not in MVP

Deferring these is what makes MVP finishable. Each is deferred in
[`spec/scope.md`](../spec/scope.md) §7 or by conformance class.

**Nine rows were added on 2026-08-19**, when the project's goal was restated as a
*demonstration people can import and configure* rather than a protocol being
hardened for adoption. Each says what would bring it back.

| Not building | Why | Class |
|---|---|---|
| **Disclosure-capacity budget** | Metered a quantity `claims.md` already conceded was defeated by collusion and correlated predicates, and no operator can say what *N* millibits permits. A **request quota** bounds probing instead. Back when a deployment asks for a subject-level cap in bits | — |
| **Contained requester runtime** | Asks agent developers to adopt a sink-mediating runtime for a benefit accruing to the custodian. A minimal test client supplies what Q2D-C-01 needs | CC-10 |
| **Direct HTTPS binding** | Superseded by the MCP binding. Re-solving transport worse is not a contribution | CC-12 |
| **Identity and the local pairing profile** | A configured key list does what the demonstration needs. MCP moved toward standard OAuth/CIMD; a bespoke pairing profile is a worse answer to a solved problem | — |
| **Escalation lifecycle** | Human approval, grants, tokens and polling are how a deployment handles a `deny` — a product feature, not a protocol primitive | — |
| **Encrypted-at-rest audit storage, and retention/deletion machinery** | Enterprise infrastructure. **A minimal local audit store is *not* cut** — see below | — |
| **Denial tier taxonomy** | Shrunk to *one refusal shape per normalized class, no cause-specific text within it* — Tier A's informative values stay distinct — the part that is true, testable and cheap. `terminology.md` §9 already forbade claiming more | — |
| **Disclosure and timing measurement** | Removes the ability to make an empirical claim in a future draft, which is the clearest cost of the reduction | — |
| **Policy-side coarsening modifiers** | Existed largely to keep capacity computable under policy narrowing. Six escalations (E-25 … E-30) were about making coarsening well-defined; they park with the budget | — |
| A2A binding | MCP is the reference binding | CC-9 |
| Credential, verifiable-computation, attested-use profiles | Deferred by scope; each needs separate cryptographic review | CC-5/6/7 |
| Store-and-forward relay, HPKE payload protection | Needs the relay profile, which 0.1 does not specify | — |
| Registry federation | Needs implementation experience first | — |
| Multi-subject policy reconciliation | No sound default exists; 0.1 fails closed | — |
| Write predicates | Read-only surface only | — |

**Compatibility mode is the MVP posture.** A deployment built to this plan may
claim *"bounded authenticated answer from a participating custodian."* It may not
claim *"answer-derived flow restricted to permitted sinks."*

**A local audit store was cut and then restored, and the reason is worth
recording.** The first draft of this reduction cut all four of
[P-011](prds/P-011-receipts-audit.md)'s audit issues on the grounds that a
demonstration returns receipts rather than storing them. Review found that
[`claims.md`](../spec/claims.md) **Q2D-C-10's *Holds when* requires the responder
to "issue a receipt for every outcome *and retain detailed audit locally*."**
Cutting the store while still claiming C-10 would have been exactly the failure
this project puts first — code delivering less than a claim states.

So the **`AuditEvent` type and a plain append-only store are back in scope**;
encryption at rest and retention/deletion stay cut. That is roughly two issues
rather than four, and it keeps C-10 true. It also confirms what the review
already suspected about this cut being the shakiest one.

**Two things this plan does not defend against, and they belong here rather than
only in the threat model.** Q2D constrains a **participating** custodian; it does
nothing about a hostile or compromised MCP server, and it is a way for an honest
custodian to prove it is honest rather than a way to constrain a dishonest one.
And a bounded answer domain closes the **response** channel only — a poisoned
tool `description` or `inputSchema` still reaches model context untouched. Both
are being added to [`claims.md`](../spec/claims.md)'s non-claims list under
**Q2D-233**.

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

### Stage 3 — Policy engine, quota, refusal shape

- Policy input/output contract; `allow` / `deny`. **No coarsening modifiers** —
  they existed largely to keep the deferred capacity budget computable, and the
  six escalations that defined them (E-25 … E-30) park with it.
- Fail-closed invariants as **property tests**, not examples: unknown scope,
  missing mandatory authority, conflicting authorities, unresolvable context.
- Restrictive composition across multiple authorities.
- **Request quota** at [`core-model.md`](../spec/core-model.md) §4 **step 9a**,
  keyed on the **relationship only** — not on anything requiring registry
  resolution, because sensitivity class is unknown until step 10 and a limiter
  that skipped unresolved predicates would leave unknown ones unlimited and
  become an existence oracle. **Required configuration with no default**; the
  server refuses to start without it, and a quota rejection is normalized like
  any other cause.
- **One refusal shape *within a configured sensitivity class***, which is what
  [`claims.md`](../spec/claims.md) Q2D-C-08 has always claimed: no cause-specific
  text, no retry guidance, no size that varies with cause. **Tier A's informative
  values stay distinct** — `malformed`, `unsupported_version` and
  `structurally_invalid` describe the requester's own message and tell it
  something it can act on ([`core-model.md`](../spec/core-model.md) §5.2.1).

**Gate:** a property test asserts no user-authored rule can override a
fail-closed invariant. A test asserts that every cause **inside a normalized
class** produces a byte-identical response, **compared across causes rather than
per cause** — the same cross-vector invariant `registry/validate.py` already
applies to registry rejections. A per-case test compares a response to itself and
cannot fail.

**Claims:** Q2D-C-08. **Not Q2D-C-09** — deferred.
· **Size:** M · **Risk:** low

**Changed 2026-08-19.** This stage was *Policy engine, budget, denial
normalization* at size L. The budget is gone and the modifier machinery with it.

**Q2D-C-08 itself is unchanged** — an earlier draft of this section said *every
refusal cause*, which is broader than the claim and contradicts §5.2.1's
deliberately informative Tier A values. What shrank is the **test surface and the
machinery**: one uniformity assertion rather than one per tier, and the
`escalation_visible` gate and timing-padding hook cut with the PRDs that consumed
them. The claim's own wording needed no edit, which is the sign the shrink was a
scope decision rather than a claim change.

---

### Stage 4 — Responder pipeline, predicates, receipts

Where the previous stages become a responder.

- The [`core-model.md`](../spec/core-model.md) §4 processing order, steps 1–19
  **and the lettered steps 5a, 9a and 11a**, in order, with the ordering itself
  asserted by test. A pipeline that runs the numbered steps and skips the
  lettered ones is unlimited probing (9a) and an unchecked registry constraint
  (11a), and would satisfy a stage defined as "1–19".
- The three registry predicates evaluated locally.
- Output validation against the effective domain; fail-closed on violation; no
  private input in any error path.
- Receipt construction and signing; local audit event distinct from and larger
  than the receipt.

**Gate:** an ordering test proves no private input is read before step 16. An
error-path test proves no private value reaches a serialized error. Receipt
digests match Stage 0 vectors.

**Claims:** Q2D-C-03, Q2D-C-04, Q2D-C-06, Q2D-C-10 · **Size:** L · **Risk:** medium

**Q2D-C-03 is now the headline claim**, and this stage is where it is enforced.
Step 17's output validation is what gives an injected payload nowhere to ride out
— see §1's walkthrough item 4 and [P-001](prds/P-001-conformance-corpus.md)'s
`injection/` groups. The claim is narrow and must stay so: it closes the
**response** channel, not the tool-description channel.

---

### Stage 5 — MCP binding and the demonstration

The last stage. Where the previous four become something somebody can import.

- **[P-017](prds/P-017-mcp-binding.md) — the MCP binding.** A library that turns
  a pinned manifest into an MCP server: the answer domain becomes the tool's
  `outputSchema`, the signed contract rides in `_meta` under `dev.q2d/`, and
  every refusal **within a normalized class** takes one shape.
- **A minimal test client** — enough to build a contract, sign it, and verify a
  response. Four issues out of [P-012](prds/P-012-requester-runtime.md), not its
  contained runtime.
- **The injection corpus** — a payload in private input, a payload through
  `public_context`, and a compromised predicate returning out-of-domain text.
- **The side-by-side demo**: the same data behind a plain MCP tool and behind
  Q2D, with the injection succeeding against one and structurally unable to reach
  the other.
- Quickstart, and the claim-language audit across every published artifact.

**Gate:** §1's walkthrough completes for someone following the quickstart and
nothing else — including item 4, the injection demonstration.

**Claims:** Q2D-C-01, via the test client's pre-evaluation commitment, which the
responder verifies. **Not Q2D-C-11** — binding equivalence is a statement
*between* bindings and this stage builds one, so it is not attributable here; a
qualifier in this cell would not survive being copied into a coverage table.
· **Size:** M · **Risk:** medium

**Changed 2026-08-19.** Stages 5 through 8 were the requester runtime, a bespoke
HTTPS daemon, the escalation lifecycle, and a measurement-bearing demonstration.
They are one stage now. The four they replace are recorded in §2 with what would
bring each back.

---

## 5. PRD set

**Seventeen PRDs; twelve active and five deferred.** Numbers are permanent once
assigned; a PRD that is abandoned keeps its number and is marked withdrawn, and a
PRD that is **deferred** keeps its number, its issues and its reasoning so a
reader can see what was planned.

| # | PRD | Stage | Size |
|---|---|---|---|
| P-001 | Conformance corpus format and harness contract | 0 | M |
| P-002 | Message envelope and canonical structures | 1 | M |
| P-003 | Cryptographic suites, key handling, downgrade policy | 1 | M |
| P-004 | Replay, expiry, idempotency | 1 | S |
| P-005 | Registry client: pinning, resolution, fail-closed | 2 | M |
| P-006 | Request validation and effective answer domain | 2 | M |
| P-007 | Policy engine contract and fail-closed invariants | 3 | M |
| P-008 | ~~Disclosure-capacity accounting~~ — **deferred** | — | — |
| P-009 | Denial normalization | 3 | S |
| P-010 | Responder pipeline, predicate execution, output validation | 4 | L |
| P-011 | Receipts and local audit | 4 | M |
| P-012 | ~~Requester runtime~~ — **deferred**; four issues survive as a test client | 5 | S |
| P-013 | ~~Direct HTTPS binding and custodian daemon~~ — **deferred**, superseded by P-017 | — | — |
| P-014 | ~~Identity and the local pairing profile~~ — **deferred** | — | — |
| P-015 | ~~Escalation lifecycle~~ — **deferred** | — | — |
| P-016 | Reference demonstration and adversarial suite | 5 | S |
| P-017 | [MCP binding](prds/P-017-mcp-binding.md) | 5 | M |

The first cut of this plan said twelve; enumerating gates grew it to sixteen,
which was itself information — Stages 1, 3 and 4 each carry more than one
separable concern. **The 2026-08-19 reduction then deferred five and added one**,
and that is information too: what it removed was the machinery around the idea
rather than the idea, and none of the five deferred PRDs is load-bearing for
Q2D-C-03 or Q2D-C-10.

**Deferred PRDs keep their issue lists.** Each carries a status header saying why
it stopped and what would bring it back. Nothing was deleted, because a reader
evaluating this project needs to see the scope that was considered as well as the
scope that was built.

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

Every implementation is written by the same author. That demonstrates the
specification is *implementable* — which is the real purpose — but it does not
make any of them *independent* in the standards sense. Describe them by count,
never as "an independent implementation", until someone unaffiliated builds one.

The discipline that makes more than one worth having is the shared corpus. Every
divergence it catches is a specification ambiguity found before an outsider finds
it.

**The count is going up, and that raises the corpus from a formality to the
load-bearing artifact.** Rust and Go exist and agree through Stage 1; a thin
Python wrapper is planned so the library is importable in the ecosystem that
would use it, and full Python and TypeScript implementations after that. With
four, every specification ambiguity costs four fixes rather than two, and nothing
but [P-001](prds/P-001-conformance-corpus.md) keeps them honest. That is the
argument for keeping P-001 at full strength through the reduction, and it is why
it gained the `injection/` groups rather than losing scope.

---

## 7. Risks

| Risk | Consequence | Mitigation |
|---|---|---|
| The corpus is written to match the first implementation | The second implementation is a port, and the corpus proves nothing | Stage 0 precedes all code. Vectors are derived from `spec/`, and every vector cites the requirement it exercises |
| Escalation semantics prove underspecified | Stage 7 stalls | Appendix C items are already open. Expect spec changes; budget for them rather than working around them |
| A PRD silently resolves a spec ambiguity | Implementations diverge while both pass their PRDs | Spec-citation rule; ambiguity is escalated to `spec/`, not decided locally |
| Policy engine scope creep | Q2D reinvents a policy language it explicitly declined to build | The engine's contract is input/output only. A rule syntax richer than the MVP needs is out of scope |
| Timing side channels never measured | A claim about denial normalization that testing does not support | **Timing measurement is cut** (2026-08-19), so nothing in this release measures the channel. `Q2D-NC-05` already concedes it remains open, and that concession is now the *whole* mitigation rather than a placeholder for a measurement. ~~Timing measurement is in Stage 8's adversarial suite, and `Q2D-NC-05` already scopes the claim honestly |

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
