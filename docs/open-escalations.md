# Open escalations register

**Non-normative.** This file records escalations — open and closed — so they can
be found in one place and closed without hunting through sixteen PRDs'
open-question tables. It is a working index, not a source of truth. Where it describes a
requirement it cites the identifier; nothing here overrides
[`spec/`](../spec/), [`registry/manifest.json`](../registry/manifest.json), or
[`docs/mvp-scope.md`](mvp-scope.md).

It exists because the alternative already failed: four escalations were decided
in conversation, the conversation ended, and nothing in the repository recorded
which four or what was decided. A register is the artifact that makes
[CLAUDE.md](../CLAUDE.md)'s *Closing an escalation* checklist runnable — you
cannot verify a decision cascaded if you cannot enumerate what it touched.

> **E-01 … E-15 and both coordination items are closed**, and their cascades are
> worked. Closed entries are kept rather than deleted: each records the options
> considered and why the losing one lost, which is the part a future reader needs
> and the part a commit message does not carry. §3 lists the resolutions.
>
> **E-36 is open**, raised while building P-002's serializer: does a string
> that carries an RFC 3339 spelling but not `core-model.md` §2.2's get refused
> *wherever* it appears, or only in the fields §2.2 names? All three
> implementations now do what §2.2 states and no more, pending the decision.
> §E-36 has the options.
>
> **E-37 is open**, from the same build: nothing in `spec/` bounds an integer,
> and both value models use a signed 64-bit one. The authoring tool now refuses
> anything outside that range so it cannot author a vector the pair cannot
> reproduce — the safe direction under either resolution, but a bound the
> specification does not state.
>
> **E-35** closed as A: §4's query order gains a lettered
> step **5a** for the header/payload comparison, symmetric with the response
> order's 4a. Adding it touched seven documents plus both schemas and both served
> copies, which is the reason it was worth escalating rather than adding in
> passing.
>
> **E-34** closed as B: `structurally_invalid`, a sixth
> Tier A value for a message that parses and is wrong in a way that is neither a
> parse failure nor an authentication one. §5.2.1 also now states the test a future value must pass — it must
> send a requester somewhere a neighbouring value would not.
>
> **E-33** closed as A, giving `core-model.md` a new
> **§5.2.1**: the `external_reason` vocabulary, five distinct Tier A values,
> `unauthenticated` for Tier B, and the registry's for Tier C. Every rejection
> vector it blocked is unblocked.
>
> **E-32** closed as A: a response payload carries
> `signature.profile` and `signature.key_id` as a query's does, and §4's response
> order gains step **4a** to compare them against the header — the check existed
> in one direction only, and the producer it catches is no less able to lie to a
> requester. Every P-001 corpus-authoring issue is unblocked.
>
> **E-31 closed as C**: the model has a signature and the suite says where it
> travels, so `eddsa-jws-2026`'s query payload carries no `signature.value`.
> P-001 issues 13 and 14 were unblocked by it, and the query half of 12.
>
> **E-29 and E-30 closed** before it, both from E-28's cascade. **E-29**: `answer_contract.maximum_cardinality` is for `set` only, and
> measures the domain's size rather than a count of results. **E-30**: a `number`
> is refused in an output schema, and a predicate whose answer is a decimal
> registers a scaled integer — so `terminology.md` §4's `scalar` shape is an
> integer.
>
> All sixteen PRDs are Ready for decomposition.
>
> **E-28 closed as A.** It grew twice on being checked — raised as a one-line
> omission in §3.2's `object` row, found to be a maximum serialized size no field
> carried while `claims.md` Q2D-C-03 claimed it was enforced, and then found to
> have a mechanism nobody had wired up. Every entry's **`output_schema`** is now
> what bounds a released value's length, §4 step 17 validates against it, and
> [`scope.md`](../spec/scope.md) §4.1 requires it to bound every variable-length
> value.
>
> **E-27 closed as A**: a release that cannot vary with the data is inadmissible
> by either route. §3.2 gains a fifth `enum` condition — *at least two labels* —
> and requires an `object` release to name at least one detail field. It had been
> a live disagreement between §3.2's conditions and
> [`registry/validate.py`](../registry/validate.py) rather than a question with
> no answer yet, and it unblocks
> [P-006](prds/P-006-request-validation.md) issue 4's `enum` half. All sixteen
> PRDs remain Ready for decomposition.
>
> **E-26 closed**, and gave `core-model.md` a new **§3.3**: two narrowings of one
> dimension compose to their greatest lower bound. Where that bound is a range no
> value satisfies, the domain is empty and fails closed — correcting §3's claim
> that narrowing alone cannot reach an empty domain. Where it is an empty
> `allowed_detail_fields`, the composition is inadmissible and fails closed —
> **E-27** decided that an `object` release names at least one detail field, for
> the same reason an `enum` coarsening needs at least two labels.
>
> **Two closed after this note was first written, and both changed behaviour an
> implementer would otherwise get wrong.** E-17 supersedes §3.2's conservative
> `enum` rule — an implementation still rejecting any requested domain not equal
> to the registered one is refusing requests §3.2 admits. E-16 moved the
> registry's JSON Schema profile into [`scope.md`](../spec/scope.md) §4.1, so it
> is no longer a property of two implementations that a third could not have
> known about.

## How to use it

Each entry carries a **Cascade** line: every document that must change when the
decision comes back. That line is the checklist. When an escalation is closed,
work it, then flip the index status and add a row to §3 naming where the
resolution landed. Keep the entry — the options and the reasoning are the record.

Status values: **Open** · **Decided — not cascaded** · **Closed**. The middle
value is the dangerous one and should never persist across a session; it is the
state this repository was in when nothing recorded which four decisions had been
made.

**Adding one:** give it the next `E-` number, and write the Cascade line *before*
the decision is made. Enumerating what a decision touches is easier while the
question is still fresh than after the answer arrives.

---

## 1. Index

| ID | Question | Raised by | Decides | Status |
|---|---|---|---|---|
| **E-01** | Do `deny` and `escalate` debit the disclosure-capacity budget? | P-008 §4.7 | `core-model.md` §9 | **Closed** |
| **E-02** | Is an approval grant single-use or multi-use? | P-015 §4.5 | `core-model.md` §5.3 | **Closed** |
| **E-03** | Does an `escalate` response carry a receipt? | P-015, P-011 | `core-model.md` §5.3, P-011 §4.1 | **Closed** |
| **E-04** | `core-model.md` §7's "even when the approval-scope digest matches" is vacuous | P-015 §4.6 | `core-model.md` §7 | **Closed** |
| **E-05** | Signed poll, or bearer token? | P-015 §4.2, P-013 | `core-model.md` | **Closed** |
| **E-06** | Drop `GET /predicates/{id}/{version}`? | P-013 §4.3 | `mvp-scope.md` §4 | **Closed** |
| **E-07** | A conformance class for the HTTPS binding, and one for identity? | P-013, P-014 | `conformance-classes.md` | **Closed** |
| **E-08** | Stage 6 attributes Q2D-C-11 to a single binding | P-013 | `mvp-scope.md` §4 | **Closed** |
| **E-09** | Stage 5 attributes "Q2D-C-12 (partial)" | P-012 | `mvp-scope.md` §4 | **Closed** |
| **E-10** | Define §2.3's three identity interfaces, or leave them named only? | P-014 | `core-model.md` §2.3 | **Closed** |
| **E-11** | `trust-matrix.md` §4's "until revocation" implies reach the profile lacks | P-014 | `trust-matrix.md` §4 | **Closed** |
| **E-12** | §3 states an intersection; §2.5 permits coarsening. Not the same operation | P-012 | `core-model.md` §3 | **Closed** |
| **E-13** | Should the `answer` response carry the effective answer domain? | P-012 | `core-model.md` §5.1 | **Closed** |
| **E-14** | Should the requester's response processing order be normative? | P-012 | `core-model.md` | **Closed** |
| **E-15** | `mvp-scope.md` §1 reads as though MVP completion is Phase 1 completion | P-016 | `mvp-scope.md` §1 | **Closed** |
| **E-16** | Should the registry's JSON Schema profile be normative in `spec/`? | P-006 | `scope.md` §4.1 (new) | **Closed** |
| **E-25** | May a policy modifier coarsen an `enum`, and if so where does its mapping live? | E-17's resolution | `core-model.md` §3.2 | **Closed** |
| **E-26** | What do two incomparable narrowings of one dimension compose to? | E-25's cascade | `core-model.md` §3, §3.3 (new) | **Closed** |
| **E-27** | Is a release that cannot vary with the data admissible — a one-label `enum`, an empty field set? | E-25's cascade | `core-model.md` §2.5, §3.2 (condition 5), §3.3 | **Closed** |
| **E-28** | What bounds an `object`, and what is the registry's `output_schema` for? | E-26's cascade | `terminology.md` §3, §4 · `core-model.md` §4 step 17 · `scope.md` §4.1 · `claims.md` Q2D-C-03 | **Closed** |
| **E-29** | Which release shapes carry `answer_contract.maximum_cardinality`? | E-28's cascade | `core-model.md` §2.5 | **Closed** |
| **E-30** | Should `scope.md` §4.1's profile gain a precision keyword, so a `number` output can be bounded? | E-28's cascade | `scope.md` §4.1 · `terminology.md` §4 | **Closed** |
| **E-31** | Is `signature.value` a field of the signed core object? | P-001 issue 12 | `core-model.md` §2.7, §5.1–§5.3 · `crypto-suites.md` §3 | **Closed** |
| **E-32** | What does a signed *response* payload contain? | E-31's cascade | `core-model.md` §5.1–§5.3, §6, §4 response step 4a (new) · `crypto-suites.md` §3 | **Closed** |
| **E-33** | What are the external denial classes a requester actually receives? | P-001 issue 12 | `core-model.md` §5.2.1 (new) · P-009 §4.1, §5 | **Closed** |
| **E-34** | Which class does a well-formed message that is not a Q2D message produce? | P-001 issue 13 | `core-model.md` §5.2.1 · `crypto-suites.md` §3 · P-003 §4.2, §6 · P-009 §4.1, §5 | **Closed** |
| **E-35** | At which §4 step does a query's header/payload comparison happen? | E-34's cascade | `core-model.md` §4 query order, §5.2.1 · `crypto-suites.md` §3 · both schemas | **Closed** |
| **E-36** | Does §2.2's timestamp spelling bind every string that looks like a timestamp, or only the fields §2.2 names? | P-002 issue 2 | `core-model.md` §2.2, §2.6 · P-002 §4.2 · `tools/author_vectors.py` · both implementations | **Open** |
| **E-37** | Does an integer in a signed structure have a range, and is it `core-model.md`'s to state? | P-002 issue 2 | `core-model.md` §2 · P-002 §4.2, §4.3 · `scope.md` §4.1 · `tools/author_vectors.py` · both implementations | **Open** |
| **E-17** | Is a coarsening mapping declared by the requester, or inferred by the responder? | P-006 | `core-model.md` §2.5, §3.2 | **Closed** |
| **E-18** | Does `harness cross` satisfy §4.8's cross-implementation clause with only byte agreement built? | P-001 §10 | P-001 §4.8, §7 | **Closed** |
| **E-19** | How is a signed vector authored, when the corpus is what an implementation is checked against? | P-001 §10 | P-001 §4.9, §10 | **Closed** |
| **E-20** | What does a vector's `wire` field assert? | P-001 §10 | `conformance/vector.schema.json`, P-009 §5 | **Closed** |
| **E-21** | Which members does the signature's protected header carry? | P-001 §10 | `crypto-suites.md` §3, `core-model.md` §2.7 | **Closed** |
| **E-22** | Are `core-model.md` §5's response field lists closed, and where does retry metadata live? | P-001 §10 | `core-model.md` §5.1, §5.2, §5.3, §9.1 | **Closed** |
| **E-23** | Which RFC 3339 spelling may a receipt timestamp use? | P-001 §10 | `core-model.md` §2.2 (new) | **Closed** |
| **E-24** | At which step is a registry-entry constraint checked when no JSON Schema can express it? | P-001 §10 | `core-model.md` §4 (new step 11a) | **Closed** |

Two further items are **coordination, not escalation** — P-001 owns both. They
are listed in §2 because they block the same PRDs, and both are now **closed**.

**E-18 … E-24 were raised while building P-001's harness and corpus**, and each
was recorded in P-001 §10 as it was raised. They are entered here late, which is
the failure this register exists to prevent: a decision recorded only in the PRD
that raised it is findable by someone already reading that PRD, and by nobody
else. Their full options and reasoning are in P-001 §10; §4 below carries the
summary and what each cascaded into.

---

## E-01 — Do `deny` and `escalate` debit the budget?

**Raised by** [P-008](prds/P-008-capacity-accounting.md) §4.7 ·
**Decides** [`core-model.md`](../spec/core-model.md) §9 ·
**Blocks** P-008 issue 5, P-015 issue 5

### Context

[`core-model.md`](../spec/core-model.md) §9 parks this with the note *"Debiting
leaks; not debiting permits free probing."* The subsetting resolution narrowed it
— a narrowing-induced out-of-domain denial is now impossible — but a policy
denial still carries information.

### Concretely

`contact/contactable-for` has an answer domain of cardinality 3: for a declared
purpose, what class of contact does the subject's policy permit. Two adversaries:

- **The prober.** An agent asks the same predicate under twenty purpose codes.
  Every one is denied. If denials are free, it has mapped the subject's purpose
  policy for nothing — twenty bits of policy structure at zero capacity cost.
- **The exhauster.** An agent sends ten thousand requests it knows will be
  denied. If denials debit, the subject's budget is gone and the *legitimate*
  restaurant-booking agent asking `dietary/menu-compatible` that evening is
  refused. The attacker never needed to receive an answer.

The second adversary is the sharper one, because the budget belongs to the
subject and the harm lands on a third party.

### Options

| | Option | For | Against |
|---|---|---|---|
| **A** | Neither debits; a separate rate limit, keyed on the same relationship, bounds probing | Correct units — what a denial leaks is not measured in bits of answer alphabet. No budget DoS. Keeps Q2D-C-09's number meaning one thing | The rate limit must then be *mandatory*, or free probing is real. Adds a second enforcement mechanism |
| **B** | Both debit | One mechanism, no second thing to configure. Probing is directly bounded | Budget DoS by a stranger. An escalation a human ultimately refuses has consumed capacity for a disclosure that never happened. Q2D-C-09's accounting stops meaning "disclosure" |
| **C** | `deny` debits, `escalate` does not | Charges the probe, spares the refused approval | Keeps the DoS. Splits one rule into two with no principled boundary |
| **D** | Neither debits; no rate limit either | Simplest | Free unlimited probing. Not defensible |

### Recommendation — A, with the rate limit named as required configuration

Two reasons, one of which is a claim-honesty reason and therefore wins under
[CLAUDE.md](../CLAUDE.md)'s priority order.

**The units argument.** Q2D-C-09 claims accounting over *disclosure*, in
millibits of answer alphabet. A denial discloses nothing from the answer
alphabet; what it leaks is policy structure, which has no bit-count in this
system. Charging it against the bit budget would be measuring one thing with
another thing's ruler, and it would make the receipt's
`disclosure_capacity_debit_millibits` a number that no longer means what
Q2D-C-09 says it means.

**The DoS asymmetry.** Under B, any party that can reach the custodian can spend
a subject's budget without ever receiving an answer. That is a disclosure-
independent harm to a third party, and no claim covers it.

**Two things the decision must carry, or A is not safe:**

1. **The rate limit is required configuration with no default**, the way
   retention is in [P-011](prds/P-011-receipts-audit.md) §4.7 and grant lifetime
   is in [P-015](prds/P-015-escalation-lifecycle.md) §4.6. A rate limit that a
   deployment can omit turns A into D.
2. **A rate-limit rejection must fall inside the Tier C normalized class**
   ([P-009](prds/P-009-denial-normalization.md) §4.2). If "you are rate limited"
   is distinguishable from "policy refused", the rate limiter becomes exactly the
   oracle it was introduced to prevent — and
   [P-009](prds/P-009-denial-normalization.md) §4.4 already forbids retry
   metadata computed from a rate limiter for the same reason. This is the part
   most likely to be got wrong in implementation, so it belongs in the decision
   rather than in a PRD.

**Cascade:** `core-model.md` §9 (row moves from parked to decided, or is struck
and stated in §5.2/§9) · `claims.md` Q2D-C-09 assumptions · P-008 §4.7 and
issue 5 · P-009 §4.2's Tier C list gains rate-limit rejection · P-015 open
question 5 and issue 5 · P-013 §4.x (the daemon enforces it) · corpus
`capacity/` negative vectors.

---

## E-02 — Is an approval grant single-use or multi-use?

**Raised by** [P-015](prds/P-015-escalation-lifecycle.md) §4.5 ·
**Decides** [`core-model.md`](../spec/core-model.md) §5.3 ·
**Blocks** P-015 issues 6 and 7, and the shape of P-007 §4.2's new `PolicyInput`
grant field

### Context

§5.3 says a grant is *time-bounded* and says nothing about how many times it may
be used. Both readings are implementable and they are different products.

### Concretely

`scheduling/availability-window` — *which is the first of these candidate slots
the subject is free for?* A restaurant's booking agent asks; policy escalates;
the subject taps **approve**.

- **Single-use:** the agent gets one answer. Asking again needs another approval.
- **Multi-use within a one-hour window:** the agent may ask forty times in that
  hour with different candidate slot sets. Each answer is one slot, each is
  individually bounded and individually debited — and forty of them is a
  substantial reconstruction of an afternoon's calendar. The subject approved
  once, for what read on screen as one question.

### Options

| | Option | For | Against |
|---|---|---|---|
| **A** | Single-use — consumed by the first successful release | What the approval interface can honestly convey. A standing permission becomes a policy rule, visible and auditable as a rule | A transient failure after approval — network drop between grant and fresh query — costs another human approval |
| **B** | Multi-use within the window | No re-prompt on transient failure. Fewer interruptions | Converts a consent decision into a capacity question. Q2D-C-09's accounting becomes the thing bounding what one approval discloses, which it was not designed for |
| **C** | Multi-use with an explicit count chosen at approval time | Honest — the human sees the number | A new field in the approval interface, a counter to revalidate atomically, and a new failure mode when the count and the window disagree |

### Recommendation — A, single-use

The test is what the approval interface can truthfully say. A prompt can say
*"tell them whether you're free on Thursday."* No prompt can honestly say *"…and
every repetition of this question for the next hour"* in a way a person absorbs
while tapping approve. Under B the disclosure a single approval authorizes is
bounded by the budget rather than by the consent, and Q2D-C-09 was never
intended to be that bound.

C is the interesting alternative and should be recorded as the shape if a
deployment ever needs it, but it is more machinery than MVP can justify: an
atomically-decremented counter is exactly the kind of state whose failure mode is
a grant that outlives its count.

The friction cost of A is real and is the safe direction to fail in — a lost
approval costs a re-prompt, a lost single-use guarantee costs a disclosure
nobody agreed to.

**Cascade:** `core-model.md` §5.3 gains a sentence · P-015 §4.4, §4.5, issues 6
and 7 · **P-007 §4.2 `PolicyInput` gains a grant field, and under A it must be
consumable rather than merely readable** — this is the dependency
[P-007](prds/P-007-policy-engine.md) §10 is holding open · P-015 corpus section
`escalation/grant/` gains a second-use vector · `terminology.md` §6 if it
defines grant.

---

## E-03 — Does an `escalate` response carry a receipt?

**Raised by** [P-015](prds/P-015-escalation-lifecycle.md) open question 2, mirrored
in [P-011](prds/P-011-receipts-audit.md) open question 6 ·
**Decides** [`core-model.md`](../spec/core-model.md) §5.3 and P-011 §4.1 in
lockstep

### Context

[P-011](prds/P-011-receipts-audit.md) §4.1's field table has *answer* and *deny*
columns only. Q2D-C-10 claims exchange-bound accountability over "one exchange".
An escalated exchange currently produces no evidence it happened.

### Concretely

Six months later, a subject asks their custodian *"who asked about me, and what
did you tell them?"* The audit log is custodian-side and answers that. But the
**requester's** evidence — the thing it can show an auditor to prove what it was
authorized to receive — is the receipt. A requester that asked, triggered a human
approval, and was told to come back has no signed artifact showing the exchange
occurred at all. If a dispute later turns on whether the requester ever asked
before the approval, neither side holds a signed record of the escalate leg.

### Options

| | Option | For | Against |
|---|---|---|---|
| **A** | Explicit `escalate` carries the reduced deny-shaped receipt with `decision_class: escalate` | Q2D-C-10 covers every exchange with no exception. Costs nothing in uniformity — explicit escalation is already not in a normalized class | One more value in `decision_class`; P-011 §4.1 gains a column |
| **B** | No receipt on `escalate` | Nothing changes | Q2D-C-10's "one exchange" has an unstated hole, which is a claim-honesty problem, not a feature gap |
| **C** | A full answer-shaped receipt | Maximum evidence | Most of the fields do not exist yet — no effective contract, no debit, no release shape. A receipt with half its fields absent is a new shape, not a reduced one |

### Recommendation — A, with one boundary stated explicitly

A is right, and the recommendation must carry the distinction that makes it safe:

> **Only *explicit* escalation gets `decision_class: escalate`.** Opaque
> escalation returns the §5.2 normalized envelope, and its receipt must be the
> ordinary deny receipt, byte-identical to every other Tier C denial.

Without that sentence, an implementer reads "escalate responses carry
`decision_class: escalate`" and applies it to both modes — at which point the
receipt reveals that a response the wire made uniform was actually an escalation,
and [P-009](prds/P-009-denial-normalization.md)'s guarantee is defeated by the
evidence attached to it. This is the failure mode worth spending a sentence on,
because the receipt is not where anyone looks for a normalization leak.

**Cascade:** `core-model.md` §5.3 · P-011 §4.1 gains an escalate column and the
opaque-mode carve-out · P-011 open question 6 closed · P-015 open question 2
closed · P-009 §4.3 gains the receipt to its uniformity assertion · corpus
`escalation/opaque/` compares receipts as well as responses ·
`claims.md` Q2D-C-10 if its wording names the response shapes.

---

## E-04 — §7's "even when the approval-scope digest matches" is vacuous

**Raised by** [P-015](prds/P-015-escalation-lifecycle.md) §4.6 ·
**Decides** [`core-model.md`](../spec/core-model.md) §7

### Context

§7 says a changed purpose, sink set, public context, predicate version, or answer
contract is a distinct request *"even when the approval-scope digest matches"*.
Under §5.3's leaning, every field §7 names is already covered by the digest — so
changing one necessarily changes the digest, and it cannot match. The clause
describes an impossible state.

### Concretely

An implementer reads §7 and reasons backwards, correctly: *the spec is telling me
these can change while the digest matches, therefore the digest must not cover
them.* They build a narrower digest — say, one omitting sink set. Now an approval
granted for *"tell them, and they may write it to their CRM"* also satisfies a
fresh query that adds a marketing-platform sink, because the digest matches. The
grant has silently widened, and every other document still reads as correct.

### Options

| | Option | For | Against |
|---|---|---|---|
| **A** | State that §7 constrains whatever list §9 eventually settles on, and is deliberately broader than §5.3's current leaning | Removes the inference without pre-empting §9 | Leaves a clause that is inert today |
| **B** | Delete the clause | No dead text | §9 may settle on a narrower list, at which point the clause was load-bearing and is gone |
| **C** | Narrow the digest to match the clause | Makes the clause meaningful | Decides §9's parked field-list question as a side effect of an editorial fix. Not defensible |

### Recommendation — A

The clause is a floor, not a description. It says *these five things always make
a distinct request, whatever the digest ends up covering* — which is exactly the
protection you want if §9 later narrows the field list. Saying so costs one
sentence and closes the wrong inference.

C is the trap: it looks like the tidy fix, and it silently resolves a parked
question the spec deliberately left open.

**Cascade:** `core-model.md` §7 · P-015 §4.6 and open question 3 · `core-model.md`
§9's approval-scope row if the note changes what it is blocked on.

---

## E-05 — Signed poll, or bearer token?

**Raised by** [P-015](prds/P-015-escalation-lifecycle.md) §4.2 open question 4;
resolves [P-013](prds/P-013-https-binding.md) open question 7 ·
**Decides** a `core-model.md` message-type addition, or a recorded weakness

### Context

Explicit escalation returns an opaque `pending_token`. Polling
`GET /pending/{token}` authenticates nobody: the token is a bearer capability.
The poll response is signed and bound to the original request digest, so whoever
holds the token learns **whether an authority approved or refused**. It is not a
Q2D response to a query and carries no receipt — and it is never the answer,
which requires a fresh query under the requester's own signature (§6, §5.3). The
disclosure is the decision, not the data.

### Concretely

Tokens travel in URLs. URLs land in proxy logs, browser history, referrer
headers, screenshots pasted into a chat, and the shell history of whoever
debugged the integration. A support engineer with access to the requester's HTTP
logs can replay the poll and read whether the subject approved — which for
`contact/contactable-for` is the subject's answer about whether they will accept
contact from this party. That is the disclosure the escalation existed to put in
front of a human, obtained by someone the human never saw.

### Options

| | Option | For | Against |
|---|---|---|---|
| **A** | Bearer token in MVP; name the weakness; signed poll later | Ships Stage 7 without inventing a core message type under time pressure. Mitigated by 128-bit entropy, short lifetime, TLS | A real weakening, and it is on the consent path — the most sensitive path in the protocol |
| **B** | Signed poll now — a small message type carrying the token under the requester's signature | Closes it properly. The outcome is released only to the principal that asked | A new core message type is a `core-model.md` addition with its own replay, expiry, and suite rules. Improvised at Stage 7 it is the kind of surface that gets a detail wrong |
| **C** | Drop explicit escalation from MVP; ship opaque only | No token, no oracle | Removes the mode a deployment uses when the disclosure is acceptable, and Stage 7's gate exercises both |

### Recommendation — A, with the weakness recorded in the threat model rather than only in the PRD

A is right for MVP and the reasoning in P-015 §4.2 holds: improvising a core
message type is worse than naming a bounded weakness. But the recommendation
should carry one addition.

**The weakness belongs in [`trust-matrix.md`](../threat-model/trust-matrix.md) §5
residual channels, not only in a PRD.** A PRD is an implementation document; the
threat model is where someone deciding whether to trust the protocol looks. A
bearer capability on the consent path that is disclosed only in P-015 §4.2 is
disclosed in the wrong place. This costs one row and is the difference between a
named limitation and one a reader finds themselves.

Worth noting for the later decision: B's message type is small, and if a core
addition is being made anyway for E-14, they are naturally the same change.

**Cascade:** P-015 §4.2 and open question 4 · P-013 open question 7 closed and
§4.5 cites it · **`trust-matrix.md` §5 gains a residual-channel row** · `claims.md`
Q2D-C-07 assumptions if polling is in scope of replay resistance · corpus
`escalation/poll/`.

---

## E-06 — Drop `GET /predicates/{id}/{version}`?

**Raised by** [P-013](prds/P-013-https-binding.md) §4.3 ·
**Decides** [`mvp-scope.md`](mvp-scope.md) §4 Stage 6 — *and it changes what gets
built*

### Context

[`mvp-scope.md`](mvp-scope.md) §4 lists four Stage 6 endpoints. P-013 §4.3 argues
the fourth is two problems: it is the existence oracle
[P-005](prds/P-005-registry-client.md) §4.7 closes, and it makes
[`core-model.md`](../spec/core-model.md) §2.4.1's entry-digest check vacuous.

### Concretely

**As an oracle:** anyone who can reach the daemon runs
`GET /.well-known/q2d/predicates/contact/contactable-for/0.1`. A 200 means this
custodian serves contact predicates; a 404 means it does not. P-005 §4.7 spends
nine failure paths and one uniform wire response ensuring a requester cannot
learn which predicates a custodian supports, because that is custodian-private
policy. This endpoint asks the question directly with none of that machinery in
the way.

**As a check-defeater:** §2.4.1 has the requester declare the digest of the entry
*it* built against, so the two parties' definitions can be compared. That works
because the copies were obtained independently —
[`scope.md`](../spec/scope.md) §4 distributes the manifest with the application.
A requester that fetches the entry *from the custodian it is about to query*
always declares a matching digest. The check P-005 §4.5 was rewritten to make
fail-closed then detects nothing, and does so silently.

### Options

| | Option | For | Against |
|---|---|---|---|
| **A** | Drop it from Stage 6 | Closes both problems. Registry distribution stays out of band, consistent with P-005 open question 4's resolution | The published report's endpoint list no longer matches the implementation — see below |
| **B** | Keep it | Matches the report; convenient for developers | Keeps an existence oracle and a vacuous integrity check. Both are findings against claims the project makes |
| **C** | Keep it authenticated and policy-gated — return only entries the requesting principal may already use | Discovery without the oracle | A second authorization surface at Stage 6, with no MVP need. The digest check stays vacuous for exactly the entries a requester can fetch |

### Recommendation — A

Two independent defects, either of which alone would justify dropping it. C is
the right shape *if* discovery is ever needed and should be recorded as such, but
it does not fix the second defect at all — a requester permitted to fetch the
entry still ends up with a matching digest by construction.

**One consequence to decide deliberately, because it is the reason this is an
escalation and not a PRD decision.** The deposited technical report lists this
endpoint (`paper/src/manuscript.md:839`, and the same line in both deposited
source packages). Those packages have a DOI and are immutable. So A means the
published 0.2.2 report describes an endpoint the reference implementation will
not have. That is acceptable and normal for a pre-release spec, but it should be
handled rather than discovered: amend `paper/src/manuscript.md` so the next draft
is correct, and note the divergence wherever the repository tells a reader how
the report relates to the current spec. **Do not edit the deposited packages.**

**Cascade:** `mvp-scope.md` §4 Stage 6 endpoint list · P-013 §4.3, §4.8, open
question 1, status, and any issue that builds it · P-005 open question 4's
resolution now has a second citation · **`paper/src/manuscript.md:839` for the
next draft** · `docs/versioning.md` if it describes report-to-spec divergence ·
`website/index.html` if it lists endpoints.

---

## E-07 — A conformance class for the HTTPS binding, and one for identity?

**Raised by** [P-013](prds/P-013-https-binding.md) open question 2 and
[P-014](prds/P-014-identity-pairing.md) open question 2 — *one decision, recorded
from both sides* ·
**Decides** [`conformance-classes.md`](../spec/conformance-classes.md)

### Context

[`conformance-classes.md`](../spec/conformance-classes.md) defines CC-8 for MCP
and CC-9 for A2A. There is no class for a direct HTTPS binding, and none for an
identity profile — CC-1 and CC-2 require delegation verification without saying
what an implementer conforms to when they supply it.

### Concretely

Stage 6 produces the reference binding: the surface every other module is
validated through, the one the quickstart drives, the one an outsider actually
runs. When they ask *"what does this daemon conform to?"*, the honest answer today
is "CC-2 and CC-3, over a transport with no class." Meanwhile Q2D-C-11's coverage
table names CC-8 and CC-9, neither of which will exist at end of MVP — so the
binding claim maps entirely onto unbuilt classes while the built binding maps
onto none.

### Options

| | Option | For | Against |
|---|---|---|---|
| **A** | Add CC-12 for the direct HTTPS binding; defer the identity class | The binding's must / must-not list already exists and is stable (P-013 §4.1–4.5). The identity boundary is what `core-model.md` §9 is still deciding | Two similar findings resolved differently, which needs its reasoning written down or it reads as inconsistent |
| **B** | Add both | Symmetric; both gaps closed | An identity class fixes the core-vs-profile boundary §9 explicitly parks. Deciding a parked spec question as a side effect of a conformance addition is the failure mode CLAUDE.md names |
| **C** | Add neither | Nothing pre-empted | The reference binding remains unclassifiable, and Stage 6 has nothing honest to report |

### Recommendation — A, and say why the two differ in the same edit

The asymmetry is principled and the reason is short: **you can write a
conformance class for a thing whose boundary is settled, and you cannot for one
whose boundary is the open question.** P-013 §4.1–4.5 is a complete must /
must-not list today. P-014's equivalent would have to state which identity
profile an implementation conforms to, and §9's parked row is precisely *"which
profile, if any, is mandatory to implement."*

Because these two findings look identical from outside, the decision should be
recorded in both PRDs *with the distinction stated*, or the next reader
reasonably concludes one of them was an oversight.

**One thing CC-12 must not do:** adding it to Q2D-C-11's owning-classes table
does not let Stage 6 claim Q2D-C-11. Equivalence needs two bindings, and a class
for one of them does not change that. See **E-08** — decide them together.

**Cascade:** `conformance-classes.md` gains CC-12 with must / must-not lists ·
its Q2D-C-11 coverage row · `claims.md` Q2D-C-11 *Verified by* · P-013 open
question 2, §4.8, status · P-014 open question 2 with the distinction stated ·
P-016 §4.6's traceability matrix and the conformance-reporting text · `mvp-scope.md`
§4 Stage 6.

---

## E-08 — Stage 6 attributes Q2D-C-11 to a single binding

**Raised by** [P-013](prds/P-013-https-binding.md) open question 2a ·
**Decides** [`mvp-scope.md`](mvp-scope.md) §4 Stage 6

### Context

[`mvp-scope.md:236`](mvp-scope.md) reads **"Claims: Q2D-C-11 (single binding;
equivalence is provable only with a second)"**. The parenthetical concedes the
claim cannot be demonstrated, and the line attributes it to the stage anyway.

### Concretely

Someone building a coverage summary — or a slide, or a README table — reads the
stage rows and lists the claims against them. The parenthetical does not survive
that copy. Q2D-C-11 appears as a Stage 6 deliverable, and the project has stated
a claim it cannot show. This is the mechanism by which overstatement enters:
nobody decided to overstate, a qualifier just did not travel.

### Options

| | Option | For | Against |
|---|---|---|---|
| **A** | Stage 6 claims none | Matches P-013 §1 and what the stage can show. Nothing to lose in transcription | A stage row with no claim looks like an omission unless it says why |
| **B** | Keep the line with the parenthetical | No change | The qualifier is one copy-paste from being lost |
| **C** | Stage 6 states CC-12 conformance instead of a claim | Says something true and useful | Only available if **E-07** adds CC-12; conflates class conformance with claim coverage unless carefully worded |

### Recommendation — A, with an explicit reason on the row

Replace the claim attribution with a short statement that Stage 6 demonstrates no
new claim, and why: Q2D-C-11 needs a second binding. An empty field invites
someone to fill it; a stated reason does not.

If E-07 lands CC-12, add it as **conformance**, in a separate field from
**claims**, so the two are not read as the same thing. That is C folded into A
rather than an alternative to it.

**Cascade:** `mvp-scope.md` §4 Stage 6 claims line · P-013 open question 2a and
§1 · P-016 §4.6 traceability matrix · any README or website coverage table (grep
`Q2D-C-11`).

---

## E-09 — Stage 5 attributes "Q2D-C-12 (partial)"

**Raised by** [P-012](prds/P-012-requester-runtime.md) open question 1 ·
**Decides** [`mvp-scope.md`](mvp-scope.md) §4 Stage 5, or `claims.md` ·
**Blocks** P-012's status and issue 9

### Context

[`mvp-scope.md:220`](mvp-scope.md) reads **"Claims: Q2D-C-01, Q2D-C-12 (partial —
evidence segregation without full sink mediation)"**.
[`claims.md`](../spec/claims.md) places Q2D-C-12 under *"Requester-side claims —
conditional"*, holding **only** under `q2d-contained-runtime-0.1`, and CC-10's
honesty rule says an implementation **must not claim** containment for any path it
does not mediate. Stage 5 does not build CC-10.

### Concretely

The Stage 5 runtime verifies signatures outside model context and hands the agent
a semantic answer. That is genuinely the *shape* of evidence segregation. What it
does not do is mediate sinks — so if the host framework writes full tool results
into a trace the model can read back, the evidence is in model context and the
runtime neither knows nor prevents it. `claims.md` names that exact failure under
Q2D-C-12's *Fails if*. "Partial" is not a state `claims.md` defines: a claim
holds under its conditions or it is a design intention.

### Options

| | Option | For | Against |
|---|---|---|---|
| **A** | Drop the Q2D-C-12 attribution from Stage 5; describe P-012 §4.4's boundary as a design intention | Matches `claims.md` and CC-10's honesty rule. No spec change | Stage 5 shows less on paper than it does in fact |
| **B** | Split Q2D-C-12 into an unconditional half and a conditional half | Lets the honest part be claimed | A change to `claims.md`, needing its own assumptions, failure modes, and executable check. New claims are the thing CLAUDE.md most restricts |
| **C** | Keep "(partial)" | No change | Introduces a claim state the spec does not define, in the document most likely to be transcribed |

### Recommendation — A, but narrower than P-012's own wording

A is right. One correction to how P-012 phrases it: its open question recommends
amending `mvp-scope.md` **"to claim nothing requester-side at Stage 5"**, and that
overshoots. Q2D-C-01 — pre-evaluation commitment — is requester-side, owned by
CC-1, unconditional, and genuinely demonstrated at Stage 5. It should stay.

The precise change is: **Stage 5 claims Q2D-C-01. The Q2D-C-12 attribution is
removed**, and §4.4's boundary is described as a design intention with no passing
test, which is how P-016 §4.6's traceability matrix already reports it.

B is worth naming as declined rather than unconsidered — an unconditional
"evidence is verified outside model context" is arguably true of the Stage 5
runtime. It is declined because the value of the claim is the sink-mediation half,
and a claim that carries the easy half under a name people will read as the whole
is worse than no claim.

**Cascade:** `mvp-scope.md` §4 Stage 5 claims line · P-012 §4.8, open question 1,
**status**, and issue 9 · P-016 §4.6 traceability matrix (already correct — verify
it stays consistent) · `claims.md` untouched under A, which is the point.

---

## E-10 — Define §2.3's three identity interfaces, or leave them named only?

**Raised by** [P-014](prds/P-014-identity-pairing.md) open question 1 ·
**Decides** [`core-model.md`](../spec/core-model.md) §2.3 ·
**Blocks** P-014's status and issues 3 and 4

### Context

§2.3 says Q2D defines *three* interfaces — principal identification, key
resolution, delegation verification — and defines only the one
[P-003](prds/P-003-crypto-suites.md) needed. P-014 §5 carries provisional
signatures for the other two and marks them explicitly as input to this question,
not a resolution of it.

### Concretely

Two implementers build identity. One collapses `identify_principal` into
`resolve_key`, returning key and principal from a single lookup — reasonable,
fewer round trips. The other keeps them separate. The first has built something
where a caller can hold a principal it never checked was paired, because the
lookup that produced the key also produced the name. Both pass every document
they have, because the document that would have distinguished them defines one
interface and names two.

### Options

| | Option | For | Against |
|---|---|---|---|
| **A** | Add all three signatures to §2.3, technology-free, using P-014 §5 as input | §2.3 already commits to three interfaces; defining them is finishing a sentence the spec started. Keeps the core-vs-profile boundary out of a PRD | Fixes shape before a second profile exists to test it against |
| **B** | Leave §2.3 prose-only; P-014 §5 carries the signatures | No spec change now | Puts the core-vs-profile boundary in a PRD — which CLAUDE.md's context hierarchy forbids, and which is how two implementations diverge while both pass their own documents |
| **C** | Define them in a separate identity-profile document | Keeps `core-model.md` small | A third location for the boundary, and §2.3 still names three interfaces it does not define |

### Recommendation — A

The cost of B is the one the repository is organised to avoid. §2.3 makes a
commitment — *three interfaces, profiles supply the technology* — and an
undefined interface is exactly where a profile quietly becomes the definition.

Two constraints on the edit:

- **Technology-free.** No key format, no transport, no pairing concept. P-014 §5's
  signatures already meet this, and the reasoning under them (why
  `identify_principal` is separate, why `verify_delegation` returns unit) is the
  part worth carrying into the spec rather than the types.
- **§9's parked row stays parked.** Defining the interfaces does not decide which
  profile is mandatory to implement. Say so in the edit, or the next reader takes
  the definition as the answer to the parked question.

**Cascade:** `core-model.md` §2.3 · `core-model.md` §9's identity row (note it is
narrowed, not closed) · P-014 §5 loses "provisional", open question 1 closed,
**status**, issues 3 and 4 · P-003 §5 cross-reference · `conformance-classes.md`
CC-1/CC-2 delegation-verification wording · relates to **E-07**'s deferred
identity class.

---

## E-11 — `trust-matrix.md` §4's "until revocation" implies reach the profile lacks

**Raised by** [P-014](prds/P-014-identity-pairing.md) open question 3 ·
**Decides** [`trust-matrix.md`](../threat-model/trust-matrix.md) §4

### Context

[`trust-matrix.md:96`](../threat-model/trust-matrix.md) says a compromised
requester or executor key defeats C-05 or C-06 *"until revocation"*. Under the
local pairing profile, revocation is
[P-014](prds/P-014-identity-pairing.md) §4.5's unpairing: local, immediate, and
with no propagation whatsoever.

### Concretely

A requester's key is stolen. The operator revokes — they unpair, on their
machine. Every *other* custodian that ever paired with that requester still holds
the binding and still accepts the attacker's signatures. There is no revocation
list, no status endpoint, no propagation. "Until revocation" reads as a bounded
window closed by an action; in this profile it is closed one machine at a time,
by hand, for machines the operator may not be able to enumerate.

A reader doing threat modelling against the matrix budgets for a window. The real
exposure is unbounded in reach and bounded only by whoever gets told.

### Options

| | Option | For | Against |
|---|---|---|---|
| **A** | Amend §4 to state that revocation under the local pairing profile is per-deployment and manual, with no propagation | The threat model says what is true. P-014 §4.5 already carries the wording to lift | A `threat-model/` change that alters meaning, so it needs deliberate sign-off — hence this entry |
| **B** | Leave §4; rely on P-014 §4.5 | No change | The document a reviewer reads for adversary analysis is the one that overstates. A PRD is not where that belongs |

### Recommendation — A

This is the cheapest entry on the list and one of the more consequential, because
the trust matrix is read by exactly the audience the project is trying not to
mislead. P-014 §4.5 already contains a usable sentence:

> A compromised requester key remains valid at every custodian that has not been
> told, by hand. There is no revocation list, no status endpoint, and no
> propagation. Revocation is per-deployment and manual.

State it as scoped to the profile, so a later profile with real revocation is not
retroactively described as having none.

**Cascade:** `trust-matrix.md` §4 row and surrounding text · P-014 open question
3, §4.5, and its citation table line 49 · `claims.md` Q2D-C-05 and Q2D-C-06
assumptions if either references revocation · `crypto-suites.md` §8's parked item.

---

## E-12 — §3 states an intersection; §2.5 permits coarsening

**Raised by** [P-012](prds/P-012-requester-runtime.md) open question 2a ·
**Decides** [`core-model.md`](../spec/core-model.md) §3

### Context

§3 states the effective domain as
`registry.canonical_domain ∩ answer_contract.domain ∩ policy_modifiers`. §2.5
permits **coarsening** and prohibits subsetting. Coarsening two-hour bands
against four-hour bands is not a set intersection — the operands are not subsets
of a common set, they are different granularities of it.

Nothing is currently *wrong* in behaviour:
[P-006](prds/P-006-request-validation.md) §4.5 implements the per-shape narrowing
rules, not the formula. But two readings both stand, and §3 is load-bearing for
Q2D-C-02 and Q2D-C-09.

### Concretely

`scheduling/availability-window`. Registry domain: exact slot. Requester asks for
two-hour bands. A policy modifier coarsens to four-hour bands.

- **Read as intersection:** {exact slots} ∩ {2h bands} ∩ {4h bands} — as sets of
  literal values this is empty, and §3 says an empty intersection fails closed.
  An implementer following the formula denies a request that should succeed.
- **Read as narrowing composition:** the coarsest wins; the effective domain is
  four-hour bands. Cardinality drops, and so does the capacity debit read from
  the registry.

The two readings differ in **whether the request succeeds** and in **what gets
debited** — so Q2D-C-09's number depends on which one an implementation picked.

### Options

| | Option | For | Against |
|---|---|---|---|
| **A** | §3 states *narrowing composition* and points at the per-shape rules P-006 §4.5 implements | Matches §2.5 and the implementation. Editorial in effect, one operation named correctly | §3 stops being a one-line formula, which is part of why it reads well |
| **B** | Leave it | No change | Two readings of a section that determines both admissibility and the capacity debit |
| **C** | Define the intersection formally over a refinement lattice, so ∩ is meaningful across granularities | Keeps the formula and makes it true | Substantial spec machinery for a v0.1, and every implementer now needs the lattice to read §3 |

### Recommendation — A

The formula is a good summary of a different operation. Naming the operation
correctly and delegating the per-shape detail is what §3 already does for
capacity in §3.1 — read the value, do not recompute it — and the same instinct
applies: state the rule, put the mechanics where they are testable.

C is where this goes if a later profile needs composition to be provably
associative across shapes. Record it as the shape; do not build it now.

**One thing this decision must fix that is currently unmarked, and is the reason
it should not wait.** [P-006](prds/P-006-request-validation.md) is
**Ready for decomposition** and its citation table (line 35) reads *"§3 |
`effective_domain` as an intersection"*, with no note that this is under
escalation. P-006 is Stage 2 — four stages before P-012 exists. An implementer
decomposing P-006 works from that table. The escalation is currently recorded on
one side only, and it is the wrong side.

**Cascade:** `core-model.md` §3 · **P-006 citation table and §4.5** · P-012 open
question 2a · P-007 open question 4 (modifier composition — "coarser wins" is the
same rule, and should cite §3 once it says so) · `terminology.md` §6's modifier
definition · `claims.md` Q2D-C-02 and Q2D-C-09 if either restates the formula ·
corpus `domain/intersection/` — including whether the section name still fits.

---

## E-13 — Should the `answer` response carry the effective answer domain?

**Raised by** [P-012](prds/P-012-requester-runtime.md) open question 2 ·
**Decides** [`core-model.md`](../spec/core-model.md) §5.1, if adopted

### Context

§5.1 carries `effective_contract_digest` — a digest of what was authorized, not
the value. A requester therefore cannot check a result against the effective
domain; it can only check it against the domain it *requested*
([P-012](prds/P-012-requester-runtime.md) §4.5's directional check).

### Concretely

A requester asks for two-hour bands. Policy coarsens to four-hour bands. The
response carries a result and a digest the requester cannot expand. It can verify
the result lies within its own two-hour request, and it cannot verify the result
conforms to the four-hour domain actually authorized — the two differ exactly
when policy narrowed something.

### Options

| | Option | For | Against |
|---|---|---|---|
| **A** | Do not add it in 0.1 | Q2D-C-03 is a responder claim, and the trust matrix already states that a compromised executor defeats C-03, C-04, and C-06 with nothing recovering it in 0.1. The check would not defend against the adversary that matters. P-012 §4.5's directional check catches ordinary divergence | A requester takes bounded output on trust, which is a real if correctly-scoped limitation |
| **B** | Add `effective_answer_domain` to §5.1 | The requester can verify conformance itself | A `core-model.md` §5.1 change, a new field in every answer — **and the field tells the requester what policy narrowed**, which is policy disclosure the protocol otherwise withholds |

### Recommendation — A, and record B's second cost

A, for the reason P-012 gives — against a compromised executor the echoed domain
is as forgeable as the result, so the check buys nothing where it matters — plus
one argument P-012 does not make and should:

**B leaks policy.** Today a requester learns that its contract was narrowed
(`effective_contract_digest` differs from what it sent) but not *how*. Under B it
learns the custodian's modifier exactly. Across repeated queries that is a map of
the policy surface, obtained legitimately from successful answers rather than
from probing denials — the channel Q2D-C-08 and the whole normalization design
exist to keep closed. That makes B's cost structural, not just a field.

Record the shape for a later profile where the executor is attested and the
verification is worth something.

**Cascade if A (recommended):** P-012 open question 2 marked closed with the
reasoning, no spec change · P-012 §4.5 cites it.
**Cascade if B:** `core-model.md` §5.1 · P-011 §4.1 receipt fields · P-012 §4.5 ·
`claims.md` Q2D-C-03 *Enforced by* · P-009 — assess the policy-disclosure channel
before adopting · corpus `message/` and `requester/outcome/`.

---

## E-14 — Should the requester's response processing order be normative?

**Raised by** [P-012](prds/P-012-requester-runtime.md) open question 4 ·
**Decides** a [`core-model.md`](../spec/core-model.md) addition

### Context

[`core-model.md`](../spec/core-model.md) §4 makes the *responder's* nineteen-step
order normative. There is no equivalent for the requester;
[P-012](prds/P-012-requester-runtime.md) §4.3 derives one from CC-1's must-list,
which is a set of obligations rather than a sequence.

### Concretely

Two requesters, both passing every CC-1 check. One verifies the response
signature, then parses the receipt. The other parses the receipt to find the
suite, then verifies. The second processes attacker-controlled bytes before
authenticating them — the exact ordering
[CLAUDE.md](../CLAUDE.md) names as a protocol-correctness invariant, and the same
class of defect §4's ordering exists to prevent on the responder side. Neither
implementation is non-conforming, because nothing says which order.

### Options

| | Option | For | Against |
|---|---|---|---|
| **A** | Add the requester-side order to `core-model.md`, mirroring §4 | Protocol surface, made checkable. Two requesters ordering differently is precisely the divergence the corpus exists to prevent, and a corpus vector cannot assert an order the spec does not state | Adds a normative section; over-constrains implementations that had latitude |
| **B** | Leave it derived in P-012 §4.3 | Nothing to specify | Puts protocol surface in a PRD. The second implementation is built from the same PRDs, so the divergence would not appear until a third party implements — the worst time to find it |

### Recommendation — A

The deciding argument is testability. Every other ordering guarantee in this
protocol is normative and has a corpus vector. This one is an obligation set with
a recommended order in an implementation document, which means the corpus cannot
assert it and the conformance harness cannot catch a violation.

Keep the addition minimal — the verify-before-parse boundary and the points at
which a response may reach a caller. It does not need to be nineteen steps to be
useful; it needs to name the orderings whose violation is a vulnerability.

Note the overlap with **E-05**: if a signed-poll message type is ever added,
it lands in the same part of the document.

**Cascade:** `core-model.md` gains a requester-order section · P-012 §4.3 becomes
a citation rather than a derivation, open question 4 closed ·
`conformance-classes.md` CC-1 references it · P-001 §4.5 — the corpus needs an
operation that can assert order · corpus `requester/` sections.

---

## E-15 — `mvp-scope.md` §1 reads as though MVP completion is Phase 1 completion

**Raised by** [P-016](prds/P-016-demonstration-adversarial.md) open question 1 ·
**Decides** [`mvp-scope.md`](mvp-scope.md) §1 ·
**Blocks** P-016's status

### Context

[`mvp-scope.md`](mvp-scope.md) §1 is titled *Definition of done* and lists a
seven-step walkthrough. [`claims.md`](../spec/claims.md)'s traceability
requirement says every claim maps to at least one executable check before Phase 1
is described as complete. [P-016](prds/P-016-demonstration-adversarial.md) §4.6
establishes that at end of MVP **three claims will have no passing test**:
Q2D-C-11 (needs a second binding), Q2D-C-12 and Q2D-C-13 (need CC-10, not built).

### Concretely

The walkthrough completes. Someone writes *"Q2D Phase 1 is done"* — in a release
note, a README line, a conference abstract. It is not a lie anyone told; §1 is
called "definition of done" and the definition was met. But `claims.md` defines
Phase 1 completion in terms of claim coverage, and three of thirteen claims have
no check. The two documents use "done" for different things, and only one of them
is read by people deciding whether to trust the protocol.

This is the same failure class as the version-number drift
[CLAUDE.md](../CLAUDE.md) documents: a statement that is locally true and
globally wrong.

### Options

| | Option | For | Against |
|---|---|---|---|
| **A** | State in §1 that MVP completion is not Phase 1 completion in `claims.md`'s terms, and name the three claims | Closes the gap where it is read. Names the three, so the reader can check | Adds a caveat to the most motivating section in the document |
| **B** | Leave it | §4.6 already reports it honestly | §4.6 is in a Stage 8 PRD. Nobody reads a PRD before writing a release note |
| **C** | Rename §1 to "MVP walkthrough" | Removes the ambiguous word | Loses a useful heading, and does not say what is still missing |

### Recommendation — A

Name the three claims explicitly rather than gesturing at "some claims". A
specific list is checkable and self-maintaining: when Q2D-C-11 gains a second
binding, someone deletes a line. "Some claims lack tests" ages into background
noise nobody updates.

C is worth folding in — *MVP walkthrough* is the more accurate heading — but it
is cosmetic without A's substance.

Because this is the project's publication surface and
[CLAUDE.md](../CLAUDE.md) names overstatement as the failure mode that costs
most, the cascade should include a grep of every public-facing artifact, not only
the spec tree.

**Cascade:** `mvp-scope.md` §1 · P-016 open question 1, §4.6, **status** ·
`claims.md` traceability section cross-reference · `README.md` and
`website/index.html` status lines · `docs/versioning.md` if it defines phase
completion.

---

## E-16 — Should the registry's JSON Schema profile be normative in `spec/`?

**Closed — A.** Raised by [P-006](prds/P-006-request-validation.md) §4.2 ·
**Decides** [`scope.md`](../spec/scope.md), or nothing ·
**Blocked** nothing; it decided where a rule lives, not what it is

### Context

[P-006](prds/P-006-request-validation.md) §4.2 restricts registry
`public_context_schema` values to a named subset of JSON Schema — `type`,
`required`, `properties`, `additionalProperties: false`, `enum`, `minItems` /
`maxItems`, `minLength` / `maxLength`, `minimum` / `maximum`, `format:
date-time`. No `$ref`, no `oneOf` / `anyOf` / `allOf` / `not`, no
`patternProperties`, no regular expressions, no remote resolution.

The restriction exists because two JSON Schema libraries disagree on edge cases,
and a disagreement here is a cross-implementation divergence in what counts as a
valid request. It **was** stated only in a PRD.

### Concretely

A third party publishes a registry whose entry uses `oneOf`. Both reference
implementations reject it, because both were built from P-006. A fourth
implementation, built from `spec/` — which is what `spec/` is for — accepts it,
and now two conforming responders disagree about whether a request is valid.
Neither is wrong by the document it was built from.

This is the failure mode [CLAUDE.md](../CLAUDE.md)'s context hierarchy exists to
prevent, with the rule sitting one level too low.

### Options

| | Option | For | Against |
|---|---|---|---|
| **A** | State the profile in [`scope.md`](../spec/scope.md) as a constraint on registry content | The rule governs what a *registry* may contain, which is protocol surface, not implementation detail. An implementer building from `spec/` alone gets it | A `spec/` addition that makes some existing-looking manifests non-conforming. Freezes the keyword list, so extending it later is a spec change |
| **B** | Leave it in P-006 | No spec change; the list can grow as predicates need it | The two implementations enforce a rule no specification states. A third implementation cannot be built correctly from `spec/` |
| **C** | State only the *principle* in `spec/` — a registry must use a profile both implementations agree on — and keep the list in P-006 | Spec stays stable | "A profile both implementations agree on" is not checkable by anyone who is not one of those implementations |

### Recommendation — A

The deciding question is what an implementer building only from `spec/` would
produce, and under B the answer is a validator that accepts manifests ours
reject. The keyword list is already stable, already satisfied by every entry in
[`registry/manifest.json`](../registry/manifest.json), and deliberately small.

Freezing it is the real cost, and it is acceptable: a predicate that needs
`oneOf` in its public-context schema is a predicate complicated enough that the
schema is not where the complexity should be resolved — which is
[P-006](prds/P-006-request-validation.md) §4.2's own argument for the restriction
in the first place.

If declined, B should be made explicit rather than left implicit: `scope.md`
should at least say that the registry schema language is profiled and name where
the profile is defined, so a third implementer knows to go looking.

**Cascade:** `scope.md` gains the profile · `core-model.md` §2.4 if it describes
what an entry may carry · P-006 §4.2 becomes a citation rather than the source ·
P-006 open question 3 closed · P-005 §4.2 (manifest load rejects an
out-of-profile schema) · `registry/validate.py` enforces it · P-001 corpus
`domain/schema/` cites the spec identifier rather than the PRD.

---

### Resolution — A, [`scope.md`](../spec/scope.md) §4.1

§4 is where `spec/` already enumerates what a registry entry carries, and where
requester-supplied expressions are already out of scope, so a keyword
restriction sits beside a boundary the document had drawn.

Stated as **principle then list**. A list alone reads as arbitrary, and the next
person with a predicate needing `patternProperties` would treat it as an
oversight rather than a decision.

### What moving it found

**Two keywords were in the manifest and not in the list** — `$schema`, and
`items` for array element schemas. P-006 §4.2 claimed every entry already fitted
the profile; of the list as written, none did. §4.1 carries both, requires
`$schema`, and pins the dialect, because two implementations validating against
different JSON Schema dialects is the same divergence the profile exists to
prevent, one level up.

`format: date-time` needed saying too: in 2020-12 `format` is an annotation
unless the Format-Assertion vocabulary is in force, so a validator could accept
any string for it. §4.1 makes it an assertion over §2.2's timestamp.

`registry/validate.py` enforces the whole profile — keywords, dialect,
`additionalProperties: false`, and the timestamp form — because the reference
manifest is what every implementation reads as an example, and an example that
drifts teaches the drift.

That is the argument for moving a rule into `spec/` in miniature: the list had
been read as complete for as long as it lived beside the implementation that
satisfied it.

### Two options considered and not taken

**Leave it in P-006.** The arrangement E-23 turned out to be: a rule living
where it does not govern.

**Put it in a registry format document.** There isn't one.
[`registry/manifest.json`](../registry/manifest.json) is data and
[`registry/README.md`](../registry/README.md) opens by saying no deployment may
pin the manifest it describes. Creating a normative format document to hold one
keyword list is a larger change than the rule warrants.

## E-17 — Is a coarsening mapping declared by the requester, or inferred?

**Closed — A, declared.** Raised by [P-006](prds/P-006-request-validation.md) §4.5 ·
**Decides** [`core-model.md`](../spec/core-model.md) §2.5 ·
**Blocked** nothing while open: §3.2 stated a conservative `enum` rule — a
requested domain must equal the registered one — which was conforming and
implementable, so P-006 stayed Ready for decomposition. **That rule is now
superseded**, and an implementation still enforcing it rejects requests §3.2
admits.

### Context

[`core-model.md`](../spec/core-model.md) §2.5 permits a requester to request a
**coarser** form of a registered domain, and §3 composes those narrowings. For an
`enum`, coarsening means mapping registered values onto a smaller set of labels —
fifteen values onto three. **Nothing says who supplies that mapping.**

[`core-model.md`](../spec/core-model.md) §3.2's per-shape table is settled for
every other shape: `scalar` reduces precision, `interval` widens granularity,
`set` lowers cardinality. Each is checkable by comparing two numbers. `enum` was
not — "is this label a coarsening of those values?" has no answer without the
mapping, so §3.2 **stated** a conservative rule (an `enum` request must equal
the registered domain) while this was open. That rule is superseded; the
resolution below is what §3.2 says now.

### Concretely

`contact/contactable-for` registers three values: `direct`, `via-assistant`,
`none`. A requester asks for two labels: `reachable`, `not-reachable`.

- **Inferred:** the responder must decide that `direct` and `via-assistant` both
  map to `reachable`. That is a semantic judgement about the predicate, made by
  code, and a second implementation could reasonably map `via-assistant` to
  `not-reachable` instead — at which point the same query returns different
  answers from two conforming responders, and the disagreement is invisible
  because both are inside their requested domain.
- **Declared:** the requester states the mapping in the answer contract, the
  responder validates it mechanically, and both implementations check the same
  thing. This is what was chosen.

[P-012](prds/P-012-requester-runtime.md) §4.5 already records the downstream
consequence: under inference, a requester cannot check an `enum` result at all,
and its conformance check degrades to shape identity.

### Resolution — A, declared

`answer_contract.coarsening` carries the mapping, as an **array of pairs** —
`[[registered_value, label], …]` — rather than an object. A registered enum
value need not be a string (`menu-compatible` registers `true` and `false`), and
an object can key only on strings; stringifying would put a conversion
convention inside a signed structure. The array form also makes the
*function* condition expressible, which an object could not: two pairs sharing a
value is a violation an object cannot represent. §3.2 states the four
conditions a responder validates it against — total, onto, non-expanding, and a
function — all of which are set comparisons and counts.

**The responder makes no judgement about what a label means.** A mapping saying
`via-assistant → not-reachable` is admissible even where a human would call it
wrong: Q2D-C-01 binds the requester to the commitment it made, and what the
responder guarantees is that the returned answer lies inside the requested
domain, not that the requester asked a sensible question. That division is what
makes the check mechanical, and mechanical is what makes two implementations
agree.

B was not defensible in a project organised around two implementations agreeing:
it puts a semantic judgement in code, on the one path where a disagreement
produces a wrong answer rather than an error, invisibly from the wire. C —
prohibiting `enum` coarsening — would have made the protocol charge a requester
for more disclosure than it asked for, since a requester needing two labels
would receive the finer answer and coarsen it locally. That cuts against
Q2D-C-09's purpose, which is a worse cost than the field.

### Capacity, which needed no new mechanism

The debit comes from the coarsened label count, looked up in the registry
entry's capacity table exactly as any varying cardinality is
([`registry/README.md`](../registry/README.md)). An entry whose `enum` may be
coarsened carries a table over every reachable label count rather than a single
value; a count the table does not cover is a registry defect and a blocker
([P-008](prds/P-008-capacity-accounting.md) §4), not something to compute.

**So coarsening is available per predicate, not immediately.** Every `enum`
entry in the reference manifest carries a single capacity value today, and §3.2
says such an entry admits no coarsening — there is no authored debit for the
smaller label count, and a responder may not compute one. Adding those tables is
registry data work, and `registry/manifest.json` semantics is its own escalation
gate, so it is deliberately not done here.

### What the interim rule was for

§3.2 rejected any `enum` request not equal to the registered domain while this
was open. That was conforming and implementable, and its purpose was precisely
that no implementation would settle the question by accident before it was
asked.

## E-25 — May a policy modifier coarsen an `enum`, and where would its mapping live?

**Raised by** E-17's resolution ·
**Decides** [`core-model.md`](../spec/core-model.md) §3.2 ·
**Decided: B — a modifier may not coarsen an `enum`.** §3.2 now carries it as a
rule with its reason, not as a position held pending a decision.

### Context

E-17 settled that a requester's `enum` coarsening is a mapping it **declares**,
in `answer_contract.coarsening`. §3.2 also says a responder applies the same
narrowing rules to a **policy modifier**.

A modifier has no answer contract. So it has nowhere to declare a mapping, and
the rule E-17 wrote does not reach it.

### Concretely

A policy authority wants a denial-sensitive predicate returned only as
`reachable` / `not-reachable`, whatever the requester asked for. Under §3.2 as
written before this note, an implementation could reject the modifier, infer a
mapping, or invent a policy-side field — three behaviours from one document, and
the second is the inference E-17 rejected for the requester.

### Options

**A. A modifier carries its own mapping**, validated by the same four
conditions against the domain it narrows.

*For:* consistent with E-17; the responder still makes no semantic judgement.
*Against:* a field added to the modifier structure ([P-007](prds/P-007-policy-engine.md)
§4), and modifiers compose — two authorities coarsening one `enum` differently
needs a composition rule §3 does not currently have for mappings.

**B. A modifier may not coarsen an `enum`** — the current conservative rule,
made permanent.

*For:* no new field, no composition question, and policy retains every other
lever it has over an `enum` (deny, escalate, or coarsen a different dimension).
*Against:* a policy authority cannot reduce an enum's disclosure without denying
outright, which is a blunt instrument where a coarsening would have been
proportionate.

### Recommendation — B, with A named as the widening. **Adopted.**

The composition problem is the deciding factor, and checking §3.2 before writing
this up made it sharper than the options above put it.

**§3's *take the coarsest* presumes the two operands are comparable**, and so
does [P-007](prds/P-007-policy-engine.md) §4.4's *coarser of the two*. For
`set` cardinality and an `interval` horizon they are — each is a single number,
and one of two numbers is the smaller. For `object` field sets, `scalar` ranges
and `interval` granularities they are not; writing this rationale is what
surfaced that, and it is **E-26** below. It does not affect the argument here,
which turns on candidates existing at all rather than on which one wins.

**An `enum` is narrowed by an arbitrary function, not a bound.** Two coarsenings
of one domain need not be comparable — `{a,b,c,d}` onto `{ab, cd}` and onto
`{ac, bd}` are both admissible under §3.2's conditions and neither factors
through the other. A common coarsening does exist — the finest partition both
refine — but for an incomparable pair it is strictly coarser than each, so its
label set is strictly smaller than either declared domain and condition 2 fails
for both. There is nothing a responder can return that either party asked for.
And that bites with **one** modifier against one requester's mapping, not only
with two modifiers, so A's real content
is a factoring rule plus a fail-closed path — not a field on `Decision`.

**The asymmetry decides the timing.** B → A accepts requests that are rejected
now, so nothing built against B breaks; A → B would break everything built on it.

**And waiting costs almost nothing.** The first version of this brief said
entries authored under B would publish capacity tables sized for
requester-reachable label counts, so adopting A later would mean re-authoring
them. That was wrong in the way that mattered:
[`registry/validate.py`](../registry/validate.py) requires an entry's capacity
table to be **total** over the counts it covers rather than sized for one
party's expected requests, so a table authored today already answers a
modifier-produced count. §3.2 now says *total* rather than *every reachable*,
which is what the validator has always enforced.

One caveat, since resolved: this depended on **E-27**, because admitting a
one-label coarsening would have given every table a `"1": 0` key and re-authored
every entry carrying one. E-27 closed the other way, so the range stands at two
through the registered cardinality and there is no migration.

The one thing B genuinely gives up: a policy authority that wants to reduce an
`enum`'s disclosure must deny or escalate instead, which is blunt where a
coarsening would have been proportionate. Revisit when a deployment can say what
it wants to happen to a mapping that does not factor — that answer is the whole
of A, and guessing it now would be inventing a rule for a case nobody has.

---

## E-26 — What do two incomparable narrowings of one dimension compose to?

**Raised by** E-25's cascade ·
**Decided: A — the greatest lower bound**, per dimension, failing closed when it
is empty. [`core-model.md`](../spec/core-model.md) **§3.3** is new and carries
it; §3's claim that narrowing alone cannot reach an empty domain is corrected.

### Context

§3 computes the effective domain as narrowing composition, *"taking the
coarsest"*. [P-007](prds/P-007-policy-engine.md) §4.4 applies that to two
modifiers: *"the result is the coarser of the two"*.

Both presume the two operands are comparable. That holds where a narrowing is a
single number — `set` `maximum_cardinality`, an `interval` horizon — because one
of two numbers is always the smaller. Three narrowings in §3.2 are not:

| Shape | §3.2 narrowing | Two that are incomparable |
|---|---|---|
| `object` | `allowed_detail_fields` a subset of registered | `{name, email}` and `{email, phone}` |
| `scalar` | a range no wider than registered | `[0, 10]` and `[5, 15]` |
| ~~`interval`~~ | ~~coarser granularity~~ | ~~two-hour and three-hour bands~~ — **wrong, see below** |

In each, neither operand is *the coarser*, and §3 does not say what the responder
produces.

**The `interval` row was wrong**, found while implementing the decision rather
than while making it. `interval` granularity is a **duration** — §3.2 says *"at
or above any registered `minimum_slot_duration`"*, and the manifest carries
`"PT30M"` — so two granularities are ranked like any two durations, and
three-hour bands satisfy a two-hour floor. It composes by taking the coarser and
was never part of this question. The row is struck rather than deleted because
the recommendation below was written around it, and the correction is the point:
the claim survived the brief, the decision, and the first draft of the spec text,
and fell to reading the registry.

Two shapes are genuinely incomparable, and both are ordered by **containment**
rather than magnitude: `object` field sets and `scalar` ranges.

**A second question rides on it, and the options below have to answer both.** §3
says composition *"cannot produce an empty domain by narrowing alone"*, which
holds when each operand narrows the one before it and retains an image. Two
authorities emitting `{name}` and `{phone}`, or `[0,10]` and `[20,30]`, break
that: whichever applies second has no image in the first's output. §3 does
already fail closed on an empty effective domain, so the behaviour is not
undefined — but the sentence saying narrowing alone cannot reach one is false as
written once modifiers can be incomparable, and it should be amended by whichever
option is chosen rather than left standing beside it.

This was found by writing E-25's rationale into §3.2, and it took three passes to
get right — which is the useful part of the history. The first draft claimed
every non-`enum` shape narrows by a parameter on an ordered ladder. Corrected to
exclude `object`, it still implied `scalar` and `interval` were fine. Corrected
again, it named all three. None of the wrong versions was obviously wrong; each
read as a reasonable summary of §3.2's table, which is how a claim like this
survives review.

### Why it matters

It is a cross-implementation divergence of exactly the kind
[`claims.md`](../spec/claims.md) Q2D-C-02 rests on not happening: the effective
domain is the responder's to compute, and two responders following the same text
would compute different ones. It is not a security hole — every candidate answer
below is *narrower* than both operands, so nothing widens — but it is a
disagreement about what a request resolves to, and the capacity debit follows
from it.

### Options

**A. Take the greatest lower bound**, per shape: intersect field sets, intersect
ranges, take a granularity coarser than both.

*For:* it always exists, is narrower than both operands, and releases nothing
either authority withheld — `{email}` is a field both permitted, `[5,10]` a range
both permitted. That makes it the same principle across all three, and it extends
§3.2's recursion unchanged. It is also what *most-restrictive composition*
already means everywhere else in the engine.
*Against:* the bound may be degenerate — an empty field set, an empty range —
which is the unsatisfiable domain §3 already fails closed on. So adding an
authority can make requests unsatisfiable, and the requester sees a normalized
denial that explains nothing. For `interval` there is a further wrinkle: the
coarsest common granularity of two-hour and three-hour bands is six-hour, which
neither authority named, so *narrower than both* and *chosen by neither* are both
true at once.

**B. Fail closed on incomparable operands** — treat it as the unsatisfiable
contract §3 already handles.

*For:* one rule for all three shapes, no new composition semantics, and it never
returns a domain neither authority chose — which is the honest reading of the
`interval` wrinkle above.
*Against:* it discards answers both authorities would have permitted. `{email}`
is releasable by each of them on their own terms, and refusing it is more
restrictive than either asked to be, which is not what most-restrictive
composition is for.

**C. Require comparability** — a deployment whose authorities can emit
incomparable narrowings is misconfigured, and the engine refuses at load.

*For:* the divergence cannot occur at runtime, and it surfaces to the operator
who can fix it rather than to a requester who cannot.
*Against:* undecidable at load in general — whether two rules *can* emit
incomparable narrowings depends on the request. Checkable only for statically
enumerable rule sets, which the fixture set is and a deployment's is not.

### Recommendation — A

A is the only option that returns something both authorities would have
permitted, and that is the test worth holding to: composition should not deny
what every participant was willing to allow.

B's cost is understated by calling it conservative. It turns a composable case
into a denial, and an engine that denies where both authorities would have
allowed is not being careful — it is wrong, in a direction that is invisible
because denials are normalized and nobody can tell it apart from a legitimate
refusal. C solves a runtime problem at load time and cannot actually do it.

The degenerate-bound case A leaves is not a new hole. §3 already fails closed on
an empty effective domain, and reaching one by intersection is the same outcome
by the same route as reaching one any other way.

**Where A stops being right:** the `interval` wrinkle was the one reservation —
six-hour bands being narrower than both operands and chosen by neither, which is
close to the reason `enum` is excluded. **Peter took A with B as the fallback for
that case**, and the fallback turned out to have nothing to apply to: `interval`
granularity is a duration, so two granularities are ranked and three-hour bands
satisfy a two-hour floor. No composed value in any remaining dimension is one an
operand did not already permit — an intersected field set and an intersected
range are both inside every operand — so the reservation dissolves and A stands
alone, unqualified.

The genuine limit is narrower and worth keeping in view: a deployment can make a
class of requests unsatisfiable by adding an authority, and the requester sees a
normalized denial that does not say so. That is intended — a denial naming which
authority narrowed what would report policy structure to a requester — but it
means an operator debugging "this used to work" has nothing in the response to
work from, and the diagnosis has to come from the audit side
([P-011](prds/P-011-receipts-audit.md)).

**Option C survives as a lint, not as semantics.** Over a statically enumerable
rule set — which [P-007](prds/P-007-policy-engine.md)'s fixture set is — flagging
an authority pair that can compose to an unsatisfiable domain is useful operator
feedback.
It is not in §3.3, because it cannot be decided for a real deployment's rules,
and a check that only works on the fixtures is a development tool rather than a
protocol rule. Noted here rather than filed: it is worth an issue if P-007's
fixtures grow enough to need it.

---

## E-27 — Is a release that cannot vary with the data admissible?

**Raised by** E-25's cascade ·
**Decided: A — inadmissible.** §3.2 gains a fifth condition on an `enum`
coarsening, *at least two labels*, and requires an `object` release to name at
least one detail field. ·
**Blocked** [P-006](prds/P-006-request-validation.md) issue 4's `enum` half,
which is now unblocked. It was a **standing disagreement between documents**
rather than an undecided question, and it silently determined a debit.

### Context

§3.2's four conditions on a declared `enum` coarsening admit a mapping onto one
label. Take a four-value domain and `[[a,x],[b,x],[c,x],[d,x]]`: total ✓, image
equals the requested `{x}` ✓, strictly smaller than four ✓, a function ✓. All
four hold. The answer is a constant — the predicate returns `x` whatever the
data says, disclosing nothing, at a capacity of `ceil(1000 × log2(1))` = **0
millibits**.

Three parts of the repository disagree about whether that is a legitimate
request:

| Where | What it says |
|---|---|
| §3.2's four conditions | admissible — every condition holds |
| §3.2's `boolean` / `attribute` rationale | not admissible — it calls a one-value domain *"the empty request"* |
| [`registry/validate.py`](../registry/validate.py) | not admissible — the capacity table must key `2 … cardinality`, and a key of `1` fails |

Two of the three are prose and one is executable, which is why nothing has caught
it: the validator's rule is right for whichever answer it assumes, and the
conditions were written for a different purpose.

### Why it matters beyond tidiness

It decides a **zero debit**. A request that discloses nothing should plausibly
cost nothing, and Q2D-C-09 accounts for the capacity of the answer alphabet, so
zero is arguably correct rather than a loophole. But *zero-debit release* is the
shape of the free oracle that E-17's subsetting resolution existed to close, and
a rule that grants one deserves to be arrived at deliberately rather than fallen
into through four conditions that happen not to exclude it.

**A second route reaches the same release.** An `object` with no detail fields
returns the same answer whatever the data says, exactly as a one-label `enum`
coarsening does, and E-26's §3.3 composes two disjoint `allowed_detail_fields`
to precisely that. Whatever is decided here has to be decided for both, or the
spec refuses a constant by one route and permits it by the other.

**This brief claimed the spec already permitted the `object` route, and it did
not.** §2.5 says `allowed_detail_fields` *"may be empty"*, which I read as
settling the `object` case in the permissive direction and framed the whole
escalation as a live inconsistency between §2.5 and §3.2. Checking the deposited
technical report before implementing the decision showed otherwise: its worked
example carries `"allowed_detail_fields": []` on a **`boolean`** request. Only
`object` has detail fields, so for every other shape an empty allowlist is the
only correct value — which is all that sentence was ever permitting. §2.5 never
addressed an empty `object`.

That makes this one open question with two routes rather than a contradiction,
and it makes A a smaller change than the brief implied: §2.5 keeps *"may be
empty"*, and the `object` rule goes where the other shape rules are, in §3.2.

An earlier draft of §3.3 had rejected an empty effective allowlist as an
"interim rule", was reverted on the same misreading, and turns out to have been
right — which is a reason to check a premise before building an argument on it,
not a reason to trust a first instinct.

It also feeds E-25's rationale in `core-model.md` §3.2, which observes that two
the collapse onto one label is the common coarsening of a *fully crossing* pair,
which is one way E-25's incomparability arises. §3.2's rationale no longer rests
on that case — it rests on the common coarsening being strictly coarser than
both, which holds for every incomparable pair — but the two escalations should
still be read together.

### Options

**A. Inadmissible — add a fifth condition: at least two labels.**

*For:* it matches what the validator already enforces and what §3.2's `boolean`
rationale already says, so it makes three documents agree by changing the one
that is least specific. A constant answer is not an answer to a predicate; it is
a refusal wearing an answer's shape, and Q2D has `deny` for that.
*Against:* a fifth condition on a list whose selling point is that all of them
are checkable by comparing sets and counting — though *"the label set has at
least two members"* is exactly that.

**B. Admissible, and its debit is zero.**

*For:* it is what the conditions already say, so nothing in the spec changes; and
it is defensible on the merits — an answer that cannot vary with the data leaks
nothing, and charging for it would overstate what the budget measures.
*Against:* `registry/validate.py` must accept a table key of `1`, and every entry
that gains a table must author `"1": 0`. More seriously, it puts a zero-debit
release path in the protocol, and the reason a requester would want one is not
obvious — which is the profile of a mechanism that gets used for something other
than its stated purpose.

**C. Admissible, but not zero-rated** — charge the registered cardinality.

*For:* removes the incentive entirely.
*Against:* it charges for disclosure that did not occur, which contradicts what
`claims.md` says the budget measures. A dishonest accounting to close a hole a
condition could close directly.

### Recommendation — A. **Adopted.**

The three documents should agree, and A moves the one that is least considered.
The four conditions were written to stop a requester inventing labels or dropping
values, not to decide whether a constant is an answer; §3.2's `boolean` rationale
*was* written about exactly that and already says no. Following it is applying
the spec's own reasoning to another shape rather than choosing between two live
positions.

B is defensible and I do not think it is wrong on the merits — a constant really
does leak nothing. It loses on the second-order point: Q2D's credibility rests on
not having release paths whose purpose nobody can state, and *"ask for an answer
that cannot depend on the data, for free"* is one. If a use for it appears, A is
a condition to remove, which is a smaller change than retro-fitting the
accounting C would need.

**Where A stops being right:** if a deployment wants a *probe* — establishing
that a predicate is answerable, with a policy that permits it and a budget that
does not charge — B is the honest way to express it, and A forces that intent
into an escalation or a denial instead. Nothing in
[P-016](prds/P-016-demonstration-adversarial.md) needs one today; if that
changes, A is one condition to remove.

**What the cascade turned out to be**, after the premise above was corrected:

- §3.2's `enum` conditions gain a fifth, *at least two labels*, with §3.2's own
  *empty request* reasoning as its justification rather than a new principle.
- §3.2's `object` row requires a **non-empty** `allowed_detail_fields`, stated
  beside the shape rules where an implementer looks for it.
- §3.3's disjoint-field-set paragraph now fails closed, which is what it said
  before it was reverted on the misreading.
- §3.2's capacity paragraph states the admissible label counts as **two through
  the registered cardinality**, bounded by conditions 5 and 3 — which is what
  [`registry/validate.py`](../registry/validate.py) has always checked. E-25's
  cascade had to leave that range unstated because this question was open.
- §2.5 keeps *"may be empty"*, with a clause naming `object` as the exception.

Nothing in [`claims.md`](../spec/claims.md) changes. Q2D-C-09 accounts for the
capacity of the answer alphabet, and closing a path to a zero-capacity release
strengthens that without altering what the claim rests on.

---

## E-28 — What bounds an `object`, and what is the registry's `output_schema` for?

**Raised by** E-26's cascade, and **re-scoped after checking it** ·
**Decides** [`terminology.md`](../spec/terminology.md) §3 and §4,
[`core-model.md`](../spec/core-model.md) §4 step 17,
[`scope.md`](../spec/scope.md) §4.1, and
[`claims.md`](../spec/claims.md) **Q2D-C-03** ·
**Decided: A — the entry's `output_schema` is the bound, and §4 step 17
validates against it.** [`scope.md`](../spec/scope.md) §4.1 now requires an
output schema to bound every variable-length value it can release, and
`claims.md` Q2D-C-03 cites that instead of a maximum serialized size.
[P-010](prds/P-010-responder-pipeline.md) issue 8 is unblocked. The
`maximum_cardinality` question it also raised is split out as **E-29**.

**This was a claim-honesty item**, which put it above spec fidelity in
[CLAUDE.md](../CLAUDE.md)'s order.

### What it was, and why that was wrong

Raised as: §2.5 says `answer_contract.maximum_cardinality` is *"For `set` and
`object`"* while §3.2's `object` row never mentions it, so may an `object`'s
cardinality be narrowed? The recommendation was **A**, a one-cell addition to
§3.2 giving `object` the same row `set` has — on the reasoning that the omission
looked like drafting rather than intent.

Peter accepted A. Checking the shape definitions before implementing it — which
the brief's own *where A stops being right* said to do — inverted the answer.

[`terminology.md`](../spec/terminology.md) §4:

| Shape | Definition |
|---|---|
| `set` | *"A bounded list or set at or below a registered **maximum cardinality**."* |
| `object` | *"A structured result with enumerated fields, each itself bounded, subject to a registered **maximum serialized size**."* |

So `object`'s bound is **size, not cardinality**. Two documents agree it has no
cardinality dimension — terminology §4 and §3.2's `object` row — and one says it
does, §2.5. A would have amended the two that agree to match the one that does
not.

### The larger finding

`object`'s actual bound has no mechanism. Searching `spec/`, `registry/` and
`docs/` for a serialized-size field returns three prose mentions and no field:

| Where | What it says | Backed by |
|---|---|---|
| [`terminology.md`](../spec/terminology.md) §4 | `object` is subject to a **registered** maximum serialized size | nothing — a registry entry has no such key |
| [`claims.md`](../spec/claims.md) **Q2D-C-03** | a released result conforms to *"shape, cardinality, precision, field allowlist, and maximum serialized size"* | nothing |
| [P-010](prds/P-010-responder-pipeline.md) §4.5 | output validation checks *"…field allowlist, serialized size"* | nothing |

`answer_contract` (§2.5) has no size field either, and §3.2's narrowing table has
no size dimension, so a policy modifier could not tighten one if it existed.

**Q2D-C-03 therefore claims enforcement of a bound the protocol cannot express.**
That is the failure mode `claims.md` exists to prevent, and it is worse than a
missing feature: an implementer building P-010's output validation would look for
the field, not find it, and either invent one or drop the check — and dropping it
is invisible, because every other part of Q2D-C-03 still passes.

### Three things found by checking the recommendation before implementing it

The first draft of this entry recommended **B**, strike the bound, *"unless
per-field bounds turn out not to bound"* — and named `attribute` as the shape to
check. Checking it, and then following what that turned up:

**1. `attribute` is unbounded by definition.** [`terminology.md`](../spec/terminology.md)
§4: *"One selected attribute value released **in full**."* §3.2 permits it no
narrowing. So an `object` containing an `attribute` field has no bound from
per-field recursion, and B as first written would have left Q2D-C-03 narrower
than the protocol needs rather than merely honest.

**2. The mechanism that would bound it exists, and nothing says it is used.**
Every registry entry carries an `output_schema`, and
[`scope.md`](../spec/scope.md) §4.1's profile — which
[`registry/validate.py`](../registry/validate.py) enforces over all three of an
entry's schemas — includes **`maxLength`** and **`maxItems`**. So an entry *can*
bound every variable-length value it releases.

What is missing is any rule that it does. `scope.md` §4 puts an output schema in
scope and §4.1 constrains its form, and neither says a responder validates a
released result against it: [`core-model.md`](../spec/core-model.md) §4 **step
17** says *"Output validated against the effective **domain**"*, and
[P-010](prds/P-010-responder-pipeline.md) §4.5's six checks do not include the
schema. Nor does anything require the bound to be *set* — the profile permits
`maxLength`, and the validator checks that a schema uses only permitted keywords
with well-formed values, not that a string carries one. So the field is
well-formed, in scope, constrained in shape, and load-bearing for nothing.

**3. `terminology.md` §3 says an answer contract carries an output schema.**
§2.5's field table does not have one — it lists `release_shape`, `domain`,
`maximum_cardinality`, `allowed_detail_fields`, `precision`, `coarsening` and
`disclosure_class`. Either the contract carries a schema and §2.5 is missing a
row, or it does not and terminology overstates what a requester commits to.

The three are one thread: the protocol has a schema mechanism for bounding
released values, and the specification never wires it up.

### Options

**A. Make `output_schema` normative.** §4 step 17 validates the released output
against the effective domain **and** the entry's `output_schema`; an entry's
schema must bound every variable-length value it can release (`maxLength` on a
string, `maxItems` on an array) — a **new** requirement, which
`registry/validate.py` would gain, since today it checks only that a schema's
keywords are in the profile and its values well formed. Q2D-C-03 then cites the
output schema instead of *"maximum serialized size"*, and terminology §4's
`object` line follows.

*For:* uses a mechanism that already exists, is already carried by every entry,
and is already profile-validated — so the change is to the documents rather than
to the format. It bounds `attribute` and free-text fields, which is the hole a
size bound was for. It also closes finding 2, which is a gap whatever is decided
here: a field that is in scope and constrained in form, with no rule saying a
responder checks a result against it, will be implemented differently by
whoever notices it.
*Against:* per-value bounds are not a single serialized-size number, so a
deployment wanting *"no answer over 4 KB"* still cannot say that; it can only
bound each field and let the total follow. Requiring `maxLength` on every string
is a real constraint on entry authors, and every current entry would need
checking (two of the three release primitives, so the cost is small today and
grows).

**B. Add a serialized-size field.** A registry entry gains a maximum serialized
size; `answer_contract` gains the matching term; §3.2's `object` row narrows it;
§3.3 composes it by taking the smaller.

*For:* makes Q2D-C-03 true exactly as written, and gives a deployment the single
number A cannot express.
*Against:* the largest change, and it puts a byte count beside a capacity story
§3.1 keeps deliberately in millibits of answer alphabet — §9 already parks the
`object` capacity calculation for related reasons. It also leaves finding 2
untouched: `output_schema` still means nothing normatively, and now there are two
bounding mechanisms.

**C. Strike the bound.** Remove maximum serialized size from Q2D-C-03,
terminology §4 and P-010 §4.5. An `object` is bounded by its field allowlist and
each field's own shape, and nothing else.

*For:* the smallest change that makes every document true.
*Against:* it is now known to be **false** that per-field shapes bound an
object — `attribute` is *released in full* — so C would state a guarantee weaker
than the one the protocol could actually offer, while leaving a free-text field
inside an object unbounded. That is honest but is the wrong direction: the
mechanism exists and is unused.

### Recommendation — A

The first draft of this entry recommended C, on the assumption that per-field
recursion bounds an object. It does not: `attribute` is released in full, so a
single such field makes the object unbounded, and striking the claim would settle
for less than the protocol can do.

A is the option that changes documents rather than formats. `output_schema` is
already on every entry and already profile-checked; what is missing is any rule
saying it is *for* anything, which finding 2 shows is a defect on its own terms.
Wiring it into §4 step 17 gives Q2D-C-03 a mechanism, gives P-010 issue 8
something to build, and removes a registry field that currently means whatever an
implementer guesses.

B is right instead if a deployment genuinely needs a total-size ceiling rather
than per-value bounds. I have not found one that does, and B does not remove the
need for A — nothing would still say a released result is checked against the
output schema.

**Where A stops being right:** if `maxLength` on every string turns out to be
unauthorable in practice — a predicate whose honest answer is a variable-length
value with no natural ceiling. That would be an argument for B, or for accepting
that such a predicate cannot use the `attribute` shape at all, which may be the
real answer and is worth deciding explicitly rather than by omission.

**Two smaller corrections rode along**, and they resolved differently:

- `terminology.md` §3 said an answer contract carries an **output schema**, with
  no such row in §2.5. **Resolved by A**: the *entry's* schema is what bounds a
  result, and a requester-supplied one would be a requester-asserted bound, which
  Q2D-C-02 says is never trusted. Struck from terminology; §2.5 gains no row.
- §2.5's `maximum_cardinality` says *"For `set` and `object`"* while terminology
  §4 gives `object` no cardinality dimension. **Not resolved here** — the
  deposited technical report's worked example carries `"maximum_cardinality": 1`
  on a **`boolean`**, which cuts against §2.5 in the opposite direction and
  suggests the field may count *results* rather than domain values. Split out as
  **E-29** rather than decided on the reading that was convenient.

---

## E-29 — Which release shapes carry `answer_contract.maximum_cardinality`?

**Raised by** E-28's cascade ·
**Decided: A — `set` only.** [`core-model.md`](../spec/core-model.md) §2.5
amended, and it now says what the field measures as well as which shape carries
it. [P-006](prds/P-006-request-validation.md) issue 4 is unblocked.

### Context

Three sources, three readings:

| Where | What it says | Implies |
|---|---|---|
| [`core-model.md`](../spec/core-model.md) §2.5 | `answer_contract.maximum_cardinality` is *"For `set` and `object`"* | two shapes carry it |
| [`terminology.md`](../spec/terminology.md) §4 | `set` is bounded *"at or below a registered maximum cardinality"*; `object` is not defined by cardinality at all | one shape carries it |
| the deposited technical report, worked example | `"release_shape": "boolean"` with `"maximum_cardinality": 1` | every shape carries it |

§3.2's narrowing table has a `maximum_cardinality` row for `set` and none for
`object`, agreeing with terminology. The reference manifest uses
`maximum_cardinality` once, on the `availability-window` predicate's *computed
answer domain* — which is a registry field, not the contract field, and is an
`interval` predicate rather than a `set` or `object`.

The report's example is the informative one, because a cardinality of **1** on a
`boolean` cannot mean *"at most one of the two values"* — every answer is one
value. It reads as *"return one result"*, which is a different quantity from
*"the domain has at most N members"*, and if that is what the field means then
§2.5's *"For `set` and `object`"* is wrong in the opposite direction to the one
E-28 assumed.

The report does not govern — [`core-model.md`](../spec/core-model.md) says so in
its header — but it is evidence of what was intended, and it was written before
either §2.5 or terminology §4.

### Options

**A. `set` only.** §2.5 amended; `object` drops it, matching terminology §4 and
§3.2.

*For:* makes three normative documents agree by changing the one outlier, and
`object`'s extent is bounded by `output_schema` after E-28, so it needs no
cardinality.
*Against:* leaves the report's `boolean` example non-conforming. That is
survivable — corrections take a new draft number — but it should be a decision
rather than a side effect.

**B. Every shape, meaning *how many results*.** §2.5 keeps the field for all
shapes; terminology §4 and §3.2 gain a line saying it counts results rather than
domain members.

*For:* matches the report, and gives a name to a quantity Q2D otherwise cannot
express: *"one answer, not a stream"*.
*Against:* §1 already says **one query, one response** with no partial answer, so
a result count above 1 has no meaning in 0.1, and a field whose only legal value
is 1 is not carrying information. It would also need a capacity story: N results
is N times the disclosure, and §3.1 says nothing about it.

**C. Strike the field from the contract.** `set` cardinality is registered and
narrowed under §3.2 like any other dimension; no contract term is needed.

*For:* smallest surface. A requester narrows cardinality through
`answer_contract.domain` the way it narrows every other dimension.
*Against:* needs checking that §3.2's `set` row can express a narrowing without
it, which it may not — the row reads *"`maximum_cardinality` at or below
registered"*, naming this field.

### Recommendation — A. **Adopted.**

It changes one line to match the two documents that already agree, and after
E-28 an `object` has a bound that is not cardinality.

**Checking the report's example before implementing made the case stronger, not
weaker.** It carries `"maximum_cardinality": 1` on a `boolean` whose `domain` is
`[false, true]`, and it is a draft artefact under *either* reading:

- Read as a **domain** size, it narrows a two-value domain to one — which §3.2's
  `boolean` row has always prohibited outright (*"none — the requested domain
  must equal the registered one"*), and which E-27 has since refused generally as
  a release that cannot vary with the data. Non-conforming, and independently of
  this question.
- Read as a **result count**, §1 admits one response and no partial answer, so
  the only legal value is 1 and the field carries no information.

So the example cannot be evidence for B. Under the reading that would have
supported B, the field is inert; under the other, the example is invalid for a
reason predating this escalation.

The reference manifest also settles what the *registry's* like-named field
means. `availability-window` carries `answer_domain.maximum_cardinality: 9`
beside a `cardinality_expression`, on a predicate whose answer is one index into
the candidate list — so it caps the **domain's** size, not a number of results.
§2.5's contract field now says the same thing explicitly, and notes that the two
are different fields.

C is tempting and probably where this ends up eventually, but §3.2's `set` row
names the field, so C is a two-document change to save one line — and it should
be made deliberately if `set` narrowing is ever revisited, not folded in here.

**Where A stops being right:** if a later draft wants a `set` predicate to return
*multiple* answers in one response — a genuinely different exchange from the one
§1 describes — then B's reading is the useful one and A will have thrown away
the field's real purpose. Nothing in the current scope wants that.


---

## E-30 — Can a `number` output be bounded, and should §4.1's profile gain a precision keyword?

**Raised by** E-28's cascade ·
**Decided: B — `number` is refused, and a decimal is registered as a scaled
integer.** [`scope.md`](../spec/scope.md) §4.1 and
[`terminology.md`](../spec/terminology.md) §4 both say so, with **A** named as
the widening. It blocked nothing; it narrowed what a predicate can answer, and
that narrowing is now stated rather than implicit in a validator rule.

### Context

E-28 made an entry's `output_schema` the bound on a released value's serialized
length. Every JSON type has something in §4.1's profile that bounds it, except
one.

`minimum` and `maximum` bound an **integer**: a range of `0 … 7` admits one
digit. They do not bound a **number**. `0.0 … 1.0` admits
`0.333333333333333333333333333…` to any length a producer cares to write, and
§4.1's profile has no `multipleOf`, no `precision`, and no other keyword that
constrains a decimal expansion.

So §4.1 as it stands cannot express a bounded `number`, and
`registry/validate.py` refuses one — the fail-closed reading, which keeps
[`claims.md`](../spec/claims.md) Q2D-C-03 true.

**That is a real narrowing.** [`terminology.md`](../spec/terminology.md) §4
defines the `scalar` shape as *"a bounded integer or **number** at registered
precision"*. A predicate returning a non-integer is contemplated by the shape
vocabulary and cannot presently declare a conforming output schema. The reference
manifest has none, so nothing is broken today.

Note also that *registered precision* already appears in two places —
`answer_contract.precision` (§2.5) and the shape definition — neither of which is
the output schema. Whether precision belongs in the schema, in the domain, or in
both is part of this question.

### Options

**A. Add `multipleOf` to §4.1's profile.** A `number` is bounded when it carries
`minimum`, `maximum` and `multipleOf`.

*For:* standard JSON Schema, already understood by every library, and it
expresses exactly the missing constraint — `multipleOf: 0.01` bounds the decimal
expansion as surely as `maximum` bounds the integer part. Smallest change that
makes the `scalar` shape usable.
*Against:* `multipleOf` on floating-point values is the one JSON Schema keyword
with known cross-library disagreement, which is precisely what §4.1's frozen
profile exists to avoid. `0.1` is not representable in binary floating point, so
two validators can disagree about whether `0.3` is a multiple of `0.1`.

**B. Refuse `number` permanently.** An output schema releases `integer` or a
string; a predicate wanting a decimal registers a scaled integer — tenths,
basis points — and says so in its question text.

*For:* no new keyword, no floating-point comparison anywhere in validation, and
it is consistent with §3.1's refusal to compute `log2` at runtime for the same
class of reason. A scaled integer is exact, and the scale is documentation.
*Against:* pushes a modelling decision onto every entry author and makes the
`scalar` shape's *"or number"* false. Terminology §4 would need amending.

**C. Add a Q2D-specific `precision` keyword**, as a count of decimal places.

*For:* avoids `multipleOf`'s floating-point comparison — a digit count is an
integer and two implementations cannot disagree about it. Matches the
`answer_contract.precision` term that already exists.
*Against:* a keyword outside JSON Schema in a document whose whole point is that
an entry's schemas are JSON Schema. A validator would have to special-case it,
and a generic tool would ignore it silently — which is worse than rejecting.

### Recommendation — B, with A named as the widening. **Adopted.**

The profile exists because two JSON Schema libraries disagreeing is a
disagreement about whether a request is valid at all, and `multipleOf` on
decimals is the clearest instance of that in the whole vocabulary. Adopting A to
bound a value would import the exact failure mode §4.1 was written to exclude.

A scaled integer is exact, needs no new keyword, and costs an entry author one
line of question text. It is the same trade §3.1 already makes in carrying
capacity as integer millibits rather than computing `log2` — and that precedent
is strong, because it was made for the same reason and has held.

C is the honest middle and I would take it over A, but a non-JSON-Schema keyword
in a JSON Schema document is a cost that outlasts the problem.

**Where B stops being right:** a predicate whose answer is irreducibly a
measurement — a temperature, a concentration — where a scaled integer is a
misrepresentation rather than an encoding. None of the three reference predicates
is like that, and the question is worth revisiting when one is, rather than
guessing now what scale it would need.

**Whichever is chosen, terminology §4's `scalar` definition is amended in the
same change** — under B it says integer, under A or C it keeps *or number* and
gains the constraint that makes it true.

### What implementing it confirmed

Nothing in the repository releases a `number` — not the three reference
predicates, and not the deposited report's worked example. So B costs nothing
today and the `scalar` shape has no user to break.

**`precision` survives B and does real work.** §3.2's `scalar` row narrows by
*"reduced precision; a range no wider than registered"*, and reduced precision on
an integer is rounding to tens or hundreds — so a scaled integer coarsens exactly
as a decimal would have. `answer_contract.precision` needed no change, which was
not obvious before checking.

**Stating the scale is a rule, not a check.** Unit confusion is B's real cost,
and no validator can decide whether prose names the right scale. §4.1 says so
rather than implying a check exists — the same treatment
[`conformance/keys/README.md`](../conformance/keys/README.md) gives the rule that
nothing derives a public key from a seed.


---

## E-31 — Is `signature.value` a field of the signed core object?

**Raised by** [P-001](prds/P-001-conformance-corpus.md) issue 12, on trying to
author the first `message/sign/` vector ·
**Decides** [`core-model.md`](../spec/core-model.md) §2.7 ·
**Decided: C — the model has a signature, the suite says where it travels.**
§2.7 keeps the field and says so; `crypto-suites.md` §3 states that
`eddsa-jws-2026`'s **query** payload has no `signature.value`. It unblocked P-001
issues 13 and 14 and the query half of 12, and raised **E-32**, which settled the
response half.

### Context

[`core-model.md`](../spec/core-model.md) §2.7 lists three signature fields as
part of the query, all required:

| Field | Required | Meaning |
|---|---|---|
| `signature.profile` | yes | The signature suite identifier |
| `signature.key_id` | yes | Resolvable under the identity profile |
| `signature.value` | yes | **Covers every field above** |

[`crypto-suites.md`](../spec/crypto-suites.md) §3 registers one suite,
`eddsa-jws-2026`, in which
[P-003](prds/P-003-crypto-suites.md) §4.1 defines:

```
signed = BASE64URL(protected_header) "." BASE64URL(payload) "." BASE64URL(signature)
```

The signature is the **third segment**. §3 says the header's `suite` and
`key_id` *"are duplicated in the signed payload — `signature.profile` and
`signature.key_id`"*, and conspicuously does not mention `signature.value`.

So: does the payload carry a `signature.value`? If it does, the field signs
itself. If it does not, §2.7 lists a required field that is absent from every
conforming message.

Nothing in `spec/` or the PRDs reconciles the two. It has gone unnoticed because
no payload has ever been serialized — this is the first attempt.

### Where it came from

The deposited technical report's worked example carries the signature **inside**
the object:

```json
"signature": {
  "profile": "eddsa-jcs-2022",
  "key_id": "did:key:z6MkRequesterAgent#key-1",
  "value": "base64url-signature"
}
```

`eddsa-jcs-2022` is a **JCS** suite — canonicalize the object, sign the
canonical bytes — and in that model an in-object `signature.value` is natural,
computed over the object with the field removed. `crypto-suites.md` §3 later
declined to register a JCS-based suite at all, on the ground that
canonicalization disagreements across language ecosystems are a classic
cross-implementation failure. The suite changed; §2.7's row did not.

That is evidence of intent rather than of correctness — the report does not
govern, and `core-model.md` says so in its header — but it explains the shape of
the mistake.

### Why more than one answer is defensible

The obvious reading is that the third segment *is* the signature and §2.7 is
stale. But `core-model.md` §2.4.1 already defines a digest **over an object with
its own digest field removed**, for the registry entry, so a self-excluding
field is an established pattern in this specification rather than an oddity —
and B below is what that pattern would produce here.

There is also a layering argument. `core-model.md`'s header says *"Signature
algorithms and serialization are not fixed here — they are named by suite in
`crypto-suites.md`"*. A §2.7 that hard-codes *"the signature is the third JWS
segment"* would put a serialization decision in the document that disclaims
them.

### Options

**A. Strike `signature.value` from §2.7.** The signature is the `signed`
string's third segment. `signature.profile` and `signature.key_id` remain payload
fields, as §3 already says.

*For:* simplest, matches the only registered suite, and matches what §3 already
implies by listing exactly two duplicated members.
*Against:* puts a JWS-shaped assumption in a document that disclaims
serialization. A future suite carrying the signature in-object would have to
re-add the field, which is the kind of churn the layering exists to avoid.

**B. Keep it, computed over the object with `signature.value` removed**, exactly
as §2.4.1 does for the entry digest. The JWS third segment carries the same
bytes.

*For:* one established pattern used twice; the core object is self-describing,
and a reader holding a parsed object can see the signature without the envelope.
*Against:* the same bytes in two places, and a verifier must either check they
agree — a new failure mode, and a new rejection reason — or pick one and let the
other drift. It also makes the payload depend on the signature that depends on
the payload, which is only non-circular because of a removal rule an implementer
must not forget.

**C. Make the location suite-dependent.** §2.7 keeps `signature.value` as part
of the *model* and says the suite defines where it travels;
`crypto-suites.md` §3 says `eddsa-jws-2026` carries it in the compact form's
third segment and therefore **not** in the payload.

*For:* respects the layering `core-model.md` claims — the model has a signature,
the suite says where it goes — and is the only option that leaves room for a
future in-object suite without amending §2.7 again. It also makes §3's silence
about `signature.value` an explicit statement rather than an omission a reader
has to notice.
*Against:* two documents to read before knowing what bytes to produce, where A
needs one.

### Recommendation — C. **Adopted.**

`core-model.md` opens by disclaiming serialization, so A contradicts the
document's own stated division of labour to save one hop. The cost of C is a
cross-reference; the cost of A is that the next suite reopens §2.7.

C also fixes the thing that made this hard to spot. §3 lists the two header
members duplicated in the payload and says nothing about the third field, so a
careful reader concludes nothing — under C, §3 says outright that
`eddsa-jws-2026`'s payload has no `signature.value`, and the question cannot be
asked again.

B I would rule out. Two copies of one signature is a divergence waiting to
happen, and the §2.4.1 precedent it leans on is not analogous: an entry digest
is computed once by a registry author over a static object, where a signature is
computed per message by one party and checked by another — the removal rule has
to be got right twice, by different code, on every message.

**Where C stops being right:** if no second suite is ever registered, C's
flexibility buys nothing and A's single-document answer is cheaper for every
implementer. That is a bet on the roadmap rather than on the design, and
[`crypto-suites.md`](../spec/crypto-suites.md) already anticipates suite
addition as a normal event — it has a registry and a versioning rule for exactly
that.

**One observation that is not part of this question**, recorded so it is not
lost: the report's example declares `eddsa-jcs-2022`, which is not a registered
suite. The report does not govern and takes corrections only in a new draft, so
nothing needs doing — but a reader coming from the report will write a profile
identifier the registry rejects.


### What the cascade turned up

**The response side had the same gap, less visibly.** §5.1, §5.2 and §5.3 each
carry a bare `signature` row reading *"Covers all of the above"*, with nothing
saying where it sits. All three now point at §2.7, so one rule covers query and
response rather than the query's being fixed and the response's left to the same
inference that produced this escalation.

§6's receipt already excluded the signature from `response_digest` — *"over the
response's semantic content … excluding the receipt and the signature"* — which
is consistent with C and was the one place the spec already treated the signature
as a thing beside the object rather than inside it.


---

## E-32 — What does a signed response payload contain?

**Raised by** E-31's cascade ·
**Decides** [`core-model.md`](../spec/core-model.md) §5.1–§5.3 and §4's response
order, and [`crypto-suites.md`](../spec/crypto-suites.md) §3 ·
**Decided: A — symmetric.** §5.1–§5.3 carry `signature.profile` and
`signature.key_id`; §4's response order gains step **4a**, comparing them against
the protected header. The response half of
[P-001](prds/P-001-conformance-corpus.md) issue 12 and every `denial/` vector are
unblocked.

### Context

E-31 settled the query: a payload is the §2 core object without
`signature.value`, and it does carry `signature.profile` and `signature.key_id`,
because §3's protected header duplicates both and
[P-003](prds/P-003-crypto-suites.md) §4.2 step 4 compares each pair after
verifying. The duplication has a job.

A response is signed the same way and specified differently. §5.1, §5.2 and §5.3
each carry one row:

| Field | Meaning |
|---|---|
| `signature` | Covers all of the above. |

No sub-fields, no `profile`, no `key_id`. And §4's **response** order — nine
steps — has no equivalent of the query's header/payload comparison:

| # | Step |
|---|---|
| 2 | Read the suite identifier; reject if below the requester's minimum acceptable policy |
| 3 | Resolve the responder key; **verify the signature over the exact signed bytes** |
| 4 | Parse the verified response object |

Steps 2 and 3 read the header. Nothing afterwards compares what it said against
what the payload says.

### Why it matters

The comparison exists on the query side to catch **a producer that signs a
payload declaring one suite or key under a header declaring another**, which §3
says *"no verifier would otherwise notice"*. That attack is symmetric: a
responder could sign a payload naming one suite under a header naming a weaker
one, and a requester following §4's response order would never look.

So this is not only a question about bytes. Either a response payload carries the
copies and a step is missing, or it does not and the asymmetry is deliberate —
and if it is deliberate, the reason belongs in the text, because the next reader
will assume symmetry.

It is also a **byte** question, which is what blocks corpus work: a
`sign_response` vector asserts an exact payload, and that payload either has a
`signature` object with two members or has none.

### Options

**A. Symmetric — a response payload carries `signature.profile` and
`signature.key_id`, and §4's response order gains a comparison step.**

*For:* closes the same hole on the same terms, and a reader who has understood
the query needs no second model. The attack §3 describes does not care which
direction the message travels.
*Against:* it is a change to §4's processing order, which
[CLAUDE.md](../CLAUDE.md) puts on the escalation list precisely because the order
is load-bearing. §5's response tables are also **closed field lists** by E-22, so
this adds to three of them.

**B. Asymmetric — a response payload carries no `signature` object; §5's
`signature` row denotes the third segment, and §3 says so.**

*For:* smallest change, and it matches what the documents say today. It is
arguably sufficient on its own terms: a requester resolves the responder key
from the header and verifies; if the signature verifies under a key the requester
already trusts for that custodian, a lie in the header about *which* key was used
does not survive verification.
*Against:* the suite lie survives. A responder naming a strong suite in the
payload and a weak one in the header is not caught, because there is no payload
copy to compare — and §4's response step 2 checks the header against the
requester's floor, which an attacker-chosen header passes by naming something
acceptable while the signature was made under something else. Whether that is
reachable depends on the suite registry having two suites, which today it does
not.

**C. Symmetric fields, no new step** — a response payload carries the copies, and
comparing them is left to P-003 rather than to §4's order.

*For:* no change to the processing order, and the fields are there for a verifier
that wants them.
*Against:* a field nothing is required to check is a field that will not be
checked, and P-001's whole discipline is that an unchecked rule is a rule that
drifts. It is the worst of both: the bytes cost of A, the guarantee of B.

### Recommendation — A. **Adopted.**

The asymmetry is not defensible as a design, only as an accident. §3 gives a
reason for the duplication that does not mention direction, and a requester is
exactly as exposed to a lying producer as a responder is — more so, arguably,
since a requester is often the less capable party.

B's defence is real but narrow: it holds only while one suite is registered.
`crypto-suites.md` has a registry and a versioning rule, so it anticipates a
second, and a rule that is safe only until the thing the document plans for
happens is not a rule to adopt deliberately.

**Where A stops being right:** if the response's protected header turns out to be
constrained in a way the query's is not — signed under a key resolved from
`target.custodian` rather than from an attacker-supplied identifier, for example
— then the header is not attacker-controlled in the same sense and the
comparison buys nothing. §4's response step 3 says *"resolve the responder key"*
without saying from where, so this is worth pinning down in the same change; it
may be that the answer makes A's step redundant and B correct for a reason
neither option currently states.


### What the cascade settled and turned up

**The reservation resolved in A's favour.** The brief said to pin down where a
requester resolves the responder key, because if a response header were not
attacker-controlled the way a query's is, the comparison would buy nothing.
`resolve_key(key_id)` is a flat lookup into a set the implementation already
trusts — [P-014](prds/P-014-identity-pairing.md) §5, and
[`crypto-suites.md`](../spec/crypto-suites.md) §3 says as much for the query
side. A response header names a key the same way a query's does, so it is
attacker-controlled in the same sense and A's step is doing real work.

**Step 4a is lettered, not numbered.** §4's response steps 5 through 9 are cited
elsewhere, and the query side already set this precedent with 9a and 11a — the
step numbers are load-bearing across the repository, and renumbering them
silently is worse than an irregular label.

**`signature_suite` overlaps `signature.profile`, and the spec now says how.**
§6's receipt already records the suite, on every outcome, so a response payload
was never entirely without one — which is why B looked more defensible than it
was. They are not redundant: `signature.profile` is the message's declaration,
compared against the header at step 4a, and `signature_suite` is the receipt's
durable record, assessable after the suite is deprecated and travelling with the
receipt wherever it is retained. §6 now says they must agree and that a response
whose two disagree is rejected — one of them is false and a verifier cannot tell
which. Without that sentence, adding `signature.profile` would have put two
authenticated suite names in one payload with nothing said about the case where
they differ.


---

## E-33 — What are the external denial classes a requester actually receives?

**Raised by** [P-001](prds/P-001-conformance-corpus.md) issue 12, on authoring
the first rejection vector ·
**Decides** [`core-model.md`](../spec/core-model.md) §5.2 and
[P-009](prds/P-009-denial-normalization.md) §4.1 ·
**Decided: A.** [`core-model.md`](../spec/core-model.md) **§5.2.1** is new and
enumerates the vocabulary: five distinct Tier A values, `unauthenticated` for
Tier B, and the pinned registry's manifest-level value for Tier C. Every
rejection vector it blocked is unblocked; `message/`'s three landed with it.

### Context

§5.2's deny response carries `external_reason`, *"the normalized class, not the
true cause"*. [P-009](prds/P-009-denial-normalization.md) §4.1 sorts every
rejection into three tiers and says what each reveals externally:

| Tier | Covers | Externally |
|---|---|---|
| **A — protocol** | Malformed envelope, unknown `q2d_version`, unacceptable suite, `routing`/`signed` mismatch, expired | **Distinct errors** |
| **B — authentication** | Unresolvable key, invalid signature, invalid or expired delegation | **One class** |
| **C — registry resolution onward** | Everything from step 10 | **One class** |
| **C, reached earlier** | Rate-limit rejection at step **9a**, before resolution — so the sensitivity class is unknown and the deployment's default value is used, which must be the one an unknown predicate produces at step 10 | **Same class** |

**None of those classes has an identifier.** P-009 declares
`external_class(tier, sensitivity) -> ExternalClass` and never gives
`ExternalClass` any members. The only value anywhere in the repository is
`unavailable`, and it exists because
[`registry/manifest.json`](../registry/manifest.json)'s `denial_normalization`
block declares it — a Tier C value, supplied by a registry.

So a vector asserting *"a `routing`/`signed` disagreement is rejected"* cannot
say what the requester receives. `wire` is required on every rejection, and its
`external_reason` would have to be invented.

### Why the registry cannot supply the missing ones

Tier C's value comes from the registry because Tier C is reached only after
resolution — by step 10 the responder holds an entry, and the entry's publisher
is the party with an interest in how precise a denial may be.

Tiers A and B are the opposite. They are rejected at steps 1 to 9, **before** a
registry entry is resolved: a malformed envelope has not named a predicate a
verifier could look up, and an unresolvable key is refused at step 4. There is no
entry to read a class from. §5.2's response still has to carry something.

They are also the tiers a requester most needs to be interoperable, since a Tier
A error is *about the requester's own bytes* — P-009 says so, arguing that a
requester learning its envelope was malformed learns nothing about the custodian.
An identifier that differed per deployment would make that feedback unusable.

### Options

**A. `spec/` enumerates Tiers A and B; the registry keeps Tier C.** A closed list
in [`core-model.md`](../spec/core-model.md) §5.2 — one identifier per Tier A
cause, one for Tier B — and Tier C stays what the resolved entry declares.

*For:* puts each class where the party that owns it can state it. Tier A and B
are protocol-level and reached before any registry is consulted, so only `spec/`
can define them; Tier C is custodian policy and already works. It makes a Tier A
error mean the same thing everywhere, which is what P-009's *"describes the
request"* argument requires to be useful.
*Against:* a closed enum in `spec/` is a thing to version. Adding a Tier A cause
later means adding an identifier, and an implementation that does not know it has
to treat it as an opaque rejection — which needs saying, or the first extension
breaks interoperability in the direction this option exists to protect.

**B. The registry declares all three tiers.** `denial_normalization` grows from
one value to a table.

*For:* one mechanism, already exists, and a deployment tunes its whole denial
surface in one place.
*Against:* it does not work for the tiers that need it. A Tier A rejection
happens before an entry is resolved, so there is no entry to read; the manifest
could carry registry-level defaults, but a requester whose envelope was rejected
as malformed may not share a registry with the custodian at all — and asking it
to fetch one to interpret an error is a fetch triggered by an unauthenticated
failure.

**C. Deployment-defined, with only uniformity normative.** `spec/` requires that
every cause in a normalized class produce an identical value and says nothing
about what the value is.

*For:* smallest specification surface, and it is honest about what Q2D-C-08
actually claims — the claim is about *indistinguishability*, not about
vocabulary.
*Against:* two conforming implementations produce different bytes for the same
rejection, so no cross-implementation vector can assert one. That is exactly the
divergence the corpus exists to catch, and it would make `message/`, `suite/` and
most of `ordering/` unassertable permanently rather than temporarily.

### Recommendation — A. **Adopted.**

C is the one to rule out first, because it reads as conservative and is not: it
makes a whole class of behaviour untestable across implementations, and Q2D-C-08
is a claim about what a requester can distinguish — which needs a fixed
vocabulary to be checkable at all, even though the claim itself is about
indistinguishability.

B fails on the mechanics rather than on the principle. The tiers that lack
identifiers are the ones reached before a registry is in hand.

A puts each class with the party that can state it, and the split is not
arbitrary: it follows exactly the line P-009 already draws between what describes
the request and what describes the custodian. The versioning cost is real and is
the thing to get right in the same change — an unknown `external_reason` must be
treated as an opaque rejection rather than as a malformed response, or the first
added cause breaks every older requester.

**Where A stops being right:** if a deployment needs to *suppress* a Tier A
distinction — to answer "malformed" for an expired request, say, because the
distinction leaks that the custodian is reachable and processing — then a fixed
enumeration is the wrong shape, and what is wanted is a floor rather than a list.
Nothing in the threat model asks for that today, and P-009's Tier A argument says
the opposite, but it is the assumption A rests on and it is worth stating.


### What writing it settled

**`unsupported_suite` is one value for two causes.** P-009's Tier A cell groups
*"unregistered or unacceptable suite"*, and §5.2.1 keeps them together with the
reason: separating them would tell a requester whether the custodian *knows* a
suite it declined, which is the custodian's minimum acceptable policy — a fact
about the custodian, on the wrong side of the line Tier A is drawn along. The
grouping was P-009's; the reason was not written down.

**The unknown-value rule was the part that needed deciding, not the names.** An
`external_reason` a requester does not recognise is an **opaque rejection** —
not a malformed response and not an error. Without that, the first value a later
version adds breaks every older requester, which would make a closed enumeration
worse than none. §5.2.1 says it, [P-012](prds/P-012-requester-runtime.md) gains
a `requester/outcome/` vector for it, and a negative-acceptance row for the
implementation that errors instead.

**`ExternalClass` is anchored.** P-009 §5 declared the type and never gave it
members; it now points at §5.2.1 and says extending it is a `spec/` change,
because a requester acts on the value and one deployment inventing a name makes
that name meaningless everywhere else.

**Step 9 had no tier, and the answer was already forced.** P-009's table covers
steps 1, 3, 6 and 8 in Tier A, 4 and 7 in Tier B, and 9a and 10-onward in Tier C
— leaving the replay check at step 9 unassigned, so its rejection had no
`external_reason` and `ordering/` step 9 was still unassertable. It is Tier C,
and not as a judgement call: [P-004](prds/P-004-replay-idempotency.md) already
makes a cache *failure* a Tier C denial, so a *detected* replay being distinct
would tell a requester whether the custodian's cache is healthy — custodian
state, which is what the class exists to withhold. §5.2.1 and P-009's table both
say so now.

**A defect of my own, found in passing:** §5.2 said *"exactly four fields"* while
its table listed six rows — E-32 split the `signature` row into three members and
did not adjust the count. The fields are still four; the sentence now says which.


---

## E-34 — Which class does a well-formed message that is not a Q2D message produce?

**Raised by** [P-001](prds/P-001-conformance-corpus.md) issue 13, on authoring
`suite/downgrade/` ·
**Decides** [`core-model.md`](../spec/core-model.md) §5.2.1 ·
**Decided: B — one new value, `structurally_invalid`.** §5.2.1 carries it as a
sixth Tier A value, and all three vectors landed.

### Context

E-33 closed §5.2.1's vocabulary. Three rejections `crypto-suites.md` §3 and
[P-003](prds/P-003-crypto-suites.md) §4.2 require have no value in it:

- a protected header carrying **`alg`**, which §3 closes the header against;
- a header declaring a **suite** the payload's `signature.profile` does not;
- a header naming a **key** the payload's `signature.key_id` does not.

P-003 §6 lists all three as cases the corpus must contain. What a requester
receives is not stated, and §5.2.1 has no cell that fits:

| Value | What §5.2.1 defines it as | Fits a mismatch? |
|---|---|---|
| `unsupported_suite` | Suite unregistered, **or** below the verifier's floor | No — in all three the declared suite is registered and acceptable, which is why the message got as far as it did |
| `unauthenticated` | Unresolvable key, invalid signature, invalid or expired delegation | No — nothing failed to authenticate. In the two disagreements the key resolved and the signature verified; the `alg` header is refused at step 3, before any of that is attempted |
| `malformed` | Envelope malformed or oversized; verified object malformed or missing a required field | Arguably — see below |

What the three share is that the message is **structurally invalid while being
authentic**, which is a category the vocabulary does not have. The `alg` case
shows it most plainly: the suite is the registered one, the signature is good,
and the message is still not a Q2D message.

### Why it is not obvious

`unsupported_suite` and `unauthenticated` are the intuitive picks — one per
field that went wrong — and both describe the *cause a reader expects* rather
than what happened. In none of the three did authentication fail: the two
disagreements are found *after* a signature verifies, and the `alg` header is
refused at step 3 without one being checked at all. Reporting either would tell a requester its credentials
failed when they did not, and would put these into a normalized class whose whole
content is that its members are indistinguishable *because they are the same kind
of failure*.

I made exactly that mistake while authoring, assigning `unsupported_suite` to the
`alg` header and to the suite mismatch and `unauthenticated` to the key mismatch,
which is how this was found.

There is also an ordering asymmetry worth noticing. Every other Tier A value is
decided before or during parsing; this one is decided after a signature verifies.
Tier A's test is *"reveals nothing about the custodian"*, not *"happens early"*,
so a late-decided Tier A value is coherent — but it is the first, and if the tier
is meant to be readable as "the cheap checks", that reading breaks here.

### Options

**A. Extend `malformed`.** A message whose header and payload disagree is not
well-formed as a Q2D message, and §5.2.1 already gives `malformed` two rejection
points, steps 1 and 5. This adds a third.

*For:* no new value, and it is true — the defect is in the message's own
construction, not in the requester's identity or the suite's acceptability. It
reads correctly to a requester debugging its producer, which is who receives it.
*Against:* `malformed` currently means *"could not be parsed as expected"*, and
these parse perfectly. Stretching it to mean "parsed, and internally
contradictory" makes one value cover two quite different producer bugs, and a
requester cannot tell which from the wire.

**B. A new distinct value**, `malformed_message` or similar, covering all three.

*For:* says what happened, and keeps `malformed` meaning what it means. One value
for all three is right for the same reason `unsupported_suite` is one value for
two causes: which part was wrong is a property of the message, and a requester
debugging its own producer has the message.
*Against:* a sixth Tier A value for cases that should never occur between correct
implementations — every one is a producer bug, and the vocabulary grows to
describe something no conforming party emits.

**C. A value per case** — three of them.

*For:* most precise, and each is actionable.
*Against:* the precision buys nothing a requester cannot get from its own
message, and three values for one class of producer bug invites the reading that
the distinction matters to the protocol. It does not.

### Recommendation — B. **Adopted.**

The vocabulary should say what happened, and neither existing value does. A
requester told `unauthenticated` when nothing failed to authenticate will look in
the wrong place, and a requester told `malformed` when its message parsed cleanly
will look almost as far off.

B over C for the reason §5.2.1 already gives about `unsupported_suite`: one value
per *kind* of failure, not per case, because which part was wrong is visible in
the message the requester itself produced.

B over A because `malformed` earns its meaning from being the parse failure, and
a vocabulary is worth having only if its values partition cleanly. Two producer
bugs that fail at different steps for different reasons should not share a name
just because neither has one yet.

**Where B stops being right:** if the vocabulary is meant to stay minimal on the
principle that a requester should distinguish only what it can act on, then a
sixth value for a case that cannot arise between correct implementations is
weight without benefit, and A is the frugal answer. That is a judgement about
what the vocabulary is *for* — a debugging aid or a decision input — and §5.2.1
does not currently say.


### What the decision also settled

**The vocabulary now says what it is for.** `structurally_invalid` is the first
value added since E-33 closed the list, and the argument for adding it was not
"the cause deserves a name" — it was that a requester told `malformed` looks at
its serializer, and one told `structurally_invalid` looks at how its header is
assembled from its payload. §5.2.1 states that as the test a future value has to
pass: **a value earns a place by sending a requester somewhere a neighbouring
value would not.** Without it, the next proposal is argued from scratch, and the
list grows by precision rather than by usefulness.

**The `unsupported_suite` precedent does not transfer, and §5.2.1 says so.**
Both are one value for several causes, but `unsupported_suite` collapses to
*withhold* something — separating its two causes would leak the custodian's
minimum acceptable policy. Nothing is withheld here: which part disagreed is in
the message the requester produced. The collapse is because the distinction is
useless on the wire, not because it is dangerous, and recording that stops the
next reader treating privacy as the reason.

**The name avoids `malformed` deliberately.** `invalid_message` or
`malformed_message` would sit beside `malformed` and mean something different,
which two implementers will blur. `structurally_invalid` cannot be misread as the
parse failure.


---

## E-35 — At which §4 step does a query's header/payload comparison happen?

**Raised by** E-34's cascade ·
**Decides** [`core-model.md`](../spec/core-model.md) §4's **query** processing
order ·
**Decided: A — a lettered query step 5a**, immediately after parsing and
symmetric with the response order's 4a. Both vectors assert it.

### Context

E-32 settled that a verifier confirms the protected header's `suite` and `key_id`
equal the payload's `signature.profile` and `signature.key_id`, in **both**
directions. On the response side it added §4's response step **4a** for it. On
the query side the check already existed —
[`crypto-suites.md`](../spec/crypto-suites.md) §3 and
[P-003](prds/P-003-crypto-suites.md) §4.2 step 4 — and §4's query order has never
had a step for it.

So the requirement is stated twice and located nowhere:

| | Requirement | Step in §4 |
|---|---|---|
| Query | `crypto-suites.md` §3, P-003 §4.2 step 4 | **none** |
| Response | `crypto-suites.md` §3, E-32 | response step **4a** |

P-003's "step 4" is its own four-step verification sequence, not a §4 step, which
is what made this easy to miss — I wrote `step: 4` into both vectors, and §4 step
4 is *"Resolve the key; verify the signature"*. The comparison cannot happen
there: the payload is not parsed until step 5.

### Why it is not just a number

A vector's `step` is a claim about ordering, and P-001 §4.8 treats a wrong one as
a failure. But the deeper reason to place it deliberately is that the comparison
sits between two things that must not be reordered: it needs the parsed payload
(so, after step 5), and it must precede anything that *acts* on the payload's
declarations. Where exactly it lands decides whether, for instance, expiry at
step 6 runs before or after a message with contradictory declarations has been
refused.

### Options

**A. A lettered step 5a**, immediately after parsing, mirroring the response
order's 4a.

*For:* symmetric with the response side, which E-32 established for the same
check with the same reasoning; lettered, so the steps below do not renumber,
which is the convention 9a and 11a already set. It places the comparison before
every step that reads a payload field, which is the property that matters.
*Against:* another lettered step in an order that now has three, and each one is
a small tax on anyone reading the list for the first time.

**B. Fold it into step 5.** *"Parse the verified core object"* becomes parse and
confirm its declarations match the header.

*For:* no new step, and it is arguably what step 5 already means — an object
whose declarations contradict the header it arrived under has not been
successfully accepted.
*Against:* step 5's whole point is that it is *only* parsing, sitting after
verification so that parser behaviour is outside the security boundary. Giving it
a second job blurs a boundary §4 draws deliberately, and the response side would
still have 4a, so the two orders would describe one check two ways.

**C. Leave it unnumbered**, with the requirement living in `crypto-suites.md` §3
and P-003 alone.

*For:* no change; the check is required and implementations that read those
documents will do it.
*Against:* §4 is the document that says what order things happen in, and a
security check with no place in it is one an implementer can position anywhere —
including after step 6 or 7, which would act on a payload whose declarations were
never checked. It also leaves the corpus permanently unable to assert the
ordering, which is what `ordering/` exists for.

### Recommendation — A. **Adopted.**

E-32 already made this call for the response and gave the reasoning: the header
is untrusted, the payload's copies are authoritative, and comparing them catches
a producer no verifier would otherwise notice. The query side needs the same
check in the same place relative to parsing, and giving it a differently-shaped
home would mean two orders describing one requirement two ways — which is how the
response side came to be missing it in the first place.

B is tempting and loses the thing step 5 is for. The separation between "verify"
and "parse" is one of §4's load-bearing boundaries, and adding a semantic check to
the parse step erodes it for no gain beyond one fewer row.

**Where A stops being right:** if §4's query order is meant to name only the
orderings whose violation is a *vulnerability* — which is what its response
counterpart says of itself — then a mismatch that cannot be exploited without
also forging a signature may not earn a row. That would argue for C plus a
sentence in §4 pointing at `crypto-suites.md` §3. Worth deciding which §4 is,
since it currently reads as exhaustive on the query side and selective on the
response side.


### What the cascade touched

**Both schemas, and both served copies.** `step`'s lettered enum is closed —
*"a vector citing step 12b would otherwise assert an ordering the specification
does not have"* — so adding a step to §4 means adding it to
`vector.schema.json` and `result.schema.json` together, or a conforming runner
could not report the step a conforming vector asserts. That pairing is the defect
E-24's cascade found the hard way, by updating one and not the other.

`result.schema.json` turns out to be **served too**, and
[`test_vector_schema.py`](../conformance/tests/test_vector_schema.py) caught the
stale copy — the second published schema, where the checklist in
[CLAUDE.md](../CLAUDE.md) names only the first.

**Six documents list the lettered steps**, and each said *9a and 11a*:
`conformance-classes.md` CC-2, `mvp-scope.md`'s Stage gate, P-010 §2 twice and
its `ordering/` row and issue 2, P-001 §5's section table and issue 14, and a
comment in `test_runner_stub.py`. A step added to §4 without them is a step no
conformance class requires and no corpus section covers.

That is worth stating as a rule rather than a list: **adding a step to §4 is a
seven-document change**, and the count is why 5a was worth escalating rather than
adding in passing.


---

## 2. Coordination items — P-001 decides, no escalation needed

Listed here because they block the same PRDs and would otherwise be tracked
nowhere. Both are **closed**; see §3.

### C-01 — Pull a minimal timing capability forward to Stage 7

[P-001](prds/P-001-conformance-corpus.md) §10 deferred timing assertions to
Stage 8, on the assumption nothing earlier needed one.
[P-015](prds/P-015-escalation-lifecycle.md) issue 4 needs one at **Stage 7**: an
opaque escalation whose response is delayed by the out-of-band prompt is
distinguishable from a plain Tier C denial on latency, and P-015 §4.1's whole
design — return immediately, dispatch the prompt on another path — is untestable
without it. Raised by [P-016](prds/P-016-demonstration-adversarial.md) open
question 2.

**Resolved: pulled forward**, minimally — an assertion that two response paths
fall within a band, not a measurement framework. P-016 keeps ownership of
measurement and reporting. A sequencing correction, not a scope change. P-001 §10
and §4.5 amended; issue 18 added.

**Cascade:** P-001 §10 and §4.5 · P-015 issue 4 · P-016 open question 2.

### C-02 — Settle the §4.5 operation vocabulary before Stage 5

[P-001](prds/P-001-conformance-corpus.md) §4.5's operation table stops at Stage 4.
P-012 through P-016 each need operations it does not have — including
`http_exchange` ([P-013](prds/P-013-https-binding.md) open question 5) and the
escalation operations. Four PRDs naming their own would diverge at the *runner*
level, where it surfaces as an unknown-operation error rather than a failing
vector: the one failure the corpus cannot catch, because the corpus is what is
broken.

**Resolved:** settle all of them in one issue before Stage 5 begins — P-001
issue 17. Both **E-06** and **E-14** change the list, and P-001 §4.5 now records
how: the registry-entry endpoint is gone, so `http_exchange` never exercises it,
and `requester/order/` needs an operation that can assert *which step* rejected
rather than only that the response was rejected.

**Cascade:** P-001 §4.5 and §10 · corpus sections of P-012 … P-016 · P-013 open
question 5.

---

## 3. Resolutions

E-01 … E-15 were decided in one pass and cascaded in the same change; every
recommendation was adopted.

E-18 … E-24 were decided one at a time while P-001's harness and corpus were
built, each raised with options and a recommendation, each **adopted as
recommended**, and each cascaded before the next was raised. E-25 followed them,
raised by E-17's own resolution rather than by a PRD. E-21, E-22, E-23 and E-24 change `spec/`; none was settled in the implementation that raised it.

| ID | Resolution | Landed in |
|---|---|---|
| **E-01** | Neither `deny` nor `escalate` debits. A rate limit bounds probing instead: checked at **step 9a**, keyed on the **relationship only** — not the full budget key, since sensitivity class is unknown before registry resolution and a limiter that skipped unresolved predicates would itself be an existence oracle — **required configuration with no default**, and its rejection normalized like any other cause in its class | `core-model.md` §9.1 (new) and §5.2 · `claims.md` Q2D-C-08, Q2D-C-09 · `conformance-classes.md` CC-2 · `terminology.md` §6 · `mvp-scope.md` Stage 3 · P-008 §4.7, P-009 §3/§4.4, P-013 §4.2/§4.6, P-015 |
| **E-02** | A grant is **single-use**, consumed at release rather than at policy time | `core-model.md` §5.3 · `terminology.md` §6 · P-015 §4.4–4.5, P-007 §4.2 (`grant` field added) |
| **E-03** | An **explicit** `escalate` carries the reduced receipt with `decision_class: escalate`. An **opaque** escalation carries the ordinary deny receipt | `core-model.md` §5.3, §6 · `claims.md` Q2D-C-10 · P-011 §4.1, P-009 §4.3, P-015 §4.1 |
| **E-04** | §7's clause is a **floor** on whatever field list §9 settles, not a description of the current digest | `core-model.md` §7 · P-015 §4.6 |
| **E-05** | Bearer token in MVP; the weakness recorded as a **residual channel in the threat model**, not only in a PRD | `trust-matrix.md` §5 · P-015 §4.2, P-013 open question 7 |
| **E-06** | `GET /predicates/{id}/{version}` **dropped** | `mvp-scope.md` §4 Stage 6 · `conformance-classes.md` CC-12 must-not · P-013 §4.3, P-005 · **divergence from the deposited report recorded in [`versioning.md`](versioning.md)** |
| **E-07** | **CC-12 added** for the direct HTTPS binding; the identity class **deferred**, with the distinction between the two written into both PRDs | `conformance-classes.md` CC-12 and the coverage table · P-013 §4.8, P-014 open question 2, P-016 §4.6 |
| **E-08** | Stage 6 claims **none**; conformance CC-12 stated in a separate field | `mvp-scope.md` §4 Stage 6 · P-013 §1, §4.8 |
| **E-09** | Stage 5 claims **Q2D-C-01 only**; the Q2D-C-12 attribution removed | `mvp-scope.md` §4 Stage 5 · P-012 §1, §4.8 |
| **E-10** | The three identity interfaces are **defined in §2.3**, technology-free; the mandatory-profile question stays parked | `core-model.md` §2.3, §9 · `conformance-classes.md` CC-1, CC-2 · `crypto-suites.md` §8 · P-014 §5 |
| **E-11** | §4 now states that revocation under the local pairing profile is per-deployment and manual, bounded by who gets told | `trust-matrix.md` §4 · P-014 §4.5 |
| **E-12** | §3 states **narrowing composition**; §3.2 carries the per-shape rules normatively in `spec/` | `core-model.md` §3, §2.5 · `claims.md` Q2D-C-02 · `terminology.md` §6 · `mvp-scope.md` Stage 2 · P-006 §2/§4.1/§4.5/§6, P-007 §4.4, P-012 §4.5, P-001 §4.2 |
| **E-13** | **Not added.** The response carries the digest, not the domain — recorded as a deliberate boundary | `core-model.md` §4.1 (closing paragraph) · P-012 open question 2 |
| **E-14** | The requester's processing order is **normative**, as §4.1, kept minimal | `core-model.md` §4.1 (new) · `conformance-classes.md` CC-1 · `mvp-scope.md` Stage 5 · P-012 §4.3, P-001 §4.5 |
| **E-15** | §1 states that MVP completion is not Phase 1 completion, **naming the three claims** | `mvp-scope.md` §1 · P-016 §4.6 |
| **C-01** | Minimal timing capability **pulled forward to Stage 7** | P-001 §4.5, §10, issue 18 · P-016 open question 2 |
| **C-02** | Operation vocabulary settled as one issue before Stage 5, **after** E-06 and E-14, both of which change the list | P-001 §4.5, issue 17 |
| **E-16** | **Yes — [`scope.md`](../spec/scope.md) §4.1**, stating the principle and then the list, in that order: a list alone reads as arbitrary and invites a later reader to treat it as an oversight. The deciding question was what an implementer building only from `spec/` produces, and under "leave it in the PRD" the answer is a validator that accepts manifests P-006 §4.2 specifies ours to reject — a difference between two documents rather than between two running programs, since neither implementation exists yet. Moving it found that **`$schema` was in every entry and not in the list**, so the PRD's claim that every entry already fitted was not quite true; §4.1 includes and requires it, and pins the dialect | `scope.md` §4.1 (new) · P-006 §4.2 now cites rather than states |
| **E-17** | **Declared.** The requester carries the mapping in `answer_contract.coarsening`, and the responder validates it against four conditions that are set comparisons and counts — total, onto, non-expanding, a function. **The responder makes no judgement about what a label means**: a mapping a human would call wrong is admissible, because Q2D-C-01 binds the requester to its own commitment and what a responder guarantees is that the answer lies inside the requested domain, not that the question was sensible. Capacity comes from the label count via the entry's capacity table, the mechanism that already exists for varying cardinality | `core-model.md` §2.5, §3.2 · `claims.md` Q2D-C-02 (enforcement description) · P-006 §4.5, §6 · P-012 §4.5, which recorded the degradation this removes |
| **E-18** | The split is **approved**: P-001 issue 9 is byte agreement between two runners, and B-verifying-A is issue 19. `harness cross` exits **3 rather than 0** when the runners agree, because the exit status is the only part of the report a release gate reads. Not redundant work — byte agreement compares A's *signer* against B's signer and exercises neither verifier, and [`mvp-scope.md`](mvp-scope.md) Stage 1's gate **is** cross-verification | P-001 §4.8, §7, issues 9 and 19 · P-002 §7, P-003 §7, P-012 §7, P-013 §7 (three of which named `harness cross` for work it does not do) |
| **E-19** | Signed vectors are authored **from the specification text**, by [`tools/author_vectors.py`](../tools/author_vectors.py), written before either implementation exists — a corpus generated from an implementation cannot check that implementation. Three disciplines carry it: never described as independent; a tool/implementation disagreement is a specification ambiguity under investigation; output is committed and thereafter authored data | P-001 §4.9, §10 · `conformance/keys/README.md` · the tool's Ed25519 is gated on RFC 8032 §7.1's published vectors |
| **E-20** | A vector may assert a **subset** of §5.2's response where response construction is not what it tests, and asserts nothing about the fields it omits; `denial/` may not, because `status` and `external_reason` are both fixed by the normalized class, so a subset there compares two constants and cannot fail | `conformance/vector.schema.json` · P-001 §4.8 · P-009 §5 · `harness lint` and `harness run` |
| **E-21** | The protected header carries **`suite` and `key_id`, and no others**. `suite` is the suite identifier, because P-003 §4.2 step 4 confirms it *equals* the payload's `signature.profile`. `key_id` is there because §4 resolves the key at step 4 while the payload's copy is unreadable until step 5 — a gap nothing had recorded. **No `alg`**, so `alg: none` is not a state the format can express, and a Q2D signed string is consequently **not a conformant JWS** but the JWS compact *form* | `crypto-suites.md` §3, §4 · `core-model.md` §2.7 · P-003 §4.1, §4.2, §6 · `tools/author_vectors.py` |
| **E-22** | **Every §5 response is a closed field list** — §5.1 with `evidence` conditional on the assurance profile named in the same response, §5.2 at four fields, §5.3's explicit escalation at five. Adding one is a specification change, on the reasoning §6 already gave for the receipt. **§5.2's retry permission is dropped**: it permitted a field whose only conforming value was uniform, no conformance class allowed the transport form, and P-009 §4.4 declined to emit any — a permission with no user is a trap | `core-model.md` §5.1, §5.2, §5.3, §9.1 · `claims.md` Q2D-C-08 (enforcement description) · P-009 §4.4, P-013 §4.2 · `harness lint` |
| **E-24** | **A step of its own: 11a**, immediately after step 11's schema validation. They are different mechanisms — step 11 runs a schema the registry supplies, and an entry's other constraints are predicate-specific logic — so folding them into one step would let an implementation satisfy §4 by running a validator and stopping, and leave a vector unable to say which rejected. Lettered as 9a is, so the numbers below do not move. **[P-006](prds/P-006-request-validation.md) already had the distinction**: §4.3 separates constraints from schemas and §5 has `validate_schema` and `check_constraints` as two functions. The specification had one step where that module always had two mechanisms | `core-model.md` §4 (step 11a), §4's invariants · P-006 §2/§4.3 · P-010 §1/§2/§4 · P-001 §4.6, §5 · `conformance/vector.schema.json`'s lettered-step enum · `tools/fold_registry.py` |
| **E-23** | **One spelling, stated once, for every timestamp in the protocol**: uppercase `T`, uppercase `Z`, second precision. The rule already existed — in P-002 §4.2, which was the only place in the repository saying `Z` while `core-model.md` said only "RFC 3339, second precision". Relocating it to §2.2 gave it the reach it lacked: **P-002's profile covers the signed payload and not `routing`**, and §4 step 8 compares `routing` against `signed`. §4 step 8 is now stated as a **byte** comparison, which one spelling makes safe — the alternative is parsing unauthenticated data above the verification line | `core-model.md` §2.2 (new), §4 step 8, §5.3, §6 · `claims.md` Q2D-C-08 · P-002 §4.2 now cites rather than states · `harness lint` |
| **E-25** | **A modifier may not coarsen an `enum`**, and the reason is composition rather than the missing field. §3's *take the coarsest* presumes comparable operands; an `enum` is narrowed by an arbitrary function, two coarsenings of one domain need not be comparable, and their common coarsening is strictly coarser than each — a label set neither declared, which condition 2 rejects — where every other shape leaves something inside both operands. Permitting policy-side coarsening therefore needs a factoring rule and a fail-closed path for mappings that do not factor — and no deployment has yet stated which it wants. Widening later breaks nothing built against the rule, and reaches no label count a requester could not: a capacity table is total over the counts it covers. Which counts those are is E-27. | `core-model.md` §3.1, §3.2 · `terminology.md` §6 · `registry/README.md` · P-006 §10 · P-007 §4.4, §10, issue 8 |
| **E-26** | **The greatest lower bound**, per dimension: the coarser value where the dimension is a number or a duration, and the **intersection** where it is a range or a field set, which are ordered by containment and so need not be comparable. Where the bound is a range no value satisfies, the domain is empty and fails closed; where it is an empty `allowed_detail_fields`, the composed value is inadmissible under §3.2's non-empty rule (E-27) and fails closed as well. `enum` cannot arise, which is what keeps the rule total. Raised naming three incomparable shapes; `interval` granularity was not one of them — it is a duration, and durations are ranked. | `core-model.md` §3 and §3.3 (new) · `terminology.md` §6 · P-006 §4.1, §5, §6, issue 6 · P-007 §4.4, §5, §10, issue 4 |
| **E-27** | **Inadmissible, by both routes.** §3.2 gains a fifth condition on an `enum` coarsening — *at least two labels* — and requires an `object` release to name at least one detail field. A constant answer is a refusal wearing an answer's shape, and §3.2 already called a one-value domain *the empty request* where it explains `boolean` and `attribute`; this applies the same reading to the two shapes that had escaped it. The escalation was briefed as a live inconsistency between §2.5 and §3.2; it was not — only `object` has detail fields, so §2.5's *may be empty* was always about the shapes that have none. | `core-model.md` §2.5, §3.2, §3.3 · `registry/validate.py` · P-006 §10, issue 4 · P-007 issue 4 |
| **E-28** | **The entry's `output_schema` is the bound.** §4 step 17 validates a released result against the effective domain *and* that schema — the domain bounds which values may be returned, the schema how long they may be — and `scope.md` §4.1 requires an output schema to bound every variable-length value it can release. Q2D-C-03 cites it instead of a *maximum serialized size*, which no field carried. Raised as a table omission, twice re-scoped by checking it: `attribute` is released *in full* so per-field recursion does not bound an object, and the mechanism that does was already on every entry with no rule pointing at it. | `terminology.md` §3, §4 · `core-model.md` §4 step 17 · `scope.md` §4.1 · `claims.md` Q2D-C-03 · `conformance-classes.md` CC-2 · `registry/validate.py` · P-010 §4.5, issue 8 |
| **E-29** | **`set` only**, and the field is the **domain's** size rather than a count of results — §1 admits one response, so a result count could carry no information. Other shapes narrow cardinality through their own dimension. The deposited report's `boolean` example, which had suggested a result count, is a draft artefact under either reading: as a domain size it narrows a two-value domain to one, which §3.2's `boolean` row has always prohibited. | `core-model.md` §2.5 · P-006 issue 4 |
| **E-30** | **`number` is refused in an output schema**; a predicate whose answer is a decimal registers a **scaled integer** and states the scale in `question_notes`. The keyword that would bound a decimal is `multipleOf`, and it is the one two JSON Schema libraries most reliably disagree about — `0.1` has no exact binary representation — which is the failure §4.1's frozen profile exists to exclude. §3.1 makes the same trade carrying capacity as integer millibits. Admitting `number` later accepts schemas refused now, so nothing authored against this breaks. | `scope.md` §4.1 · `terminology.md` §4 · `registry/validate.py` |
| **E-31** | **The model has a signature; the suite says where it travels.** §2.7 keeps `signature.value` and states that, and `crypto-suites.md` §3 says `eddsa-jws-2026` carries it in the compact form's third segment and therefore not in the payload — a payload carrying it would sign itself. §5.1–§5.3's response `signature` rows point at the same rule. The alternative of striking the field would have put a JWS assumption in the document that disclaims serialization, and the next suite would reopen it. | `core-model.md` §2.7, §5.1, §5.2, §5.3 · `crypto-suites.md` §3 · P-001 issues 12, 13, 14 |
| **E-32** | **Symmetric.** A response payload carries `signature.profile` and `signature.key_id` exactly as a query's does, and §4's response order gains step **4a** to compare them against the protected header. The check catches a producer signing a payload declaring one suite or key under a header declaring another, and that producer is no less able to lie to a requester than to a responder — the check had existed in one direction only. §6 reconciles the receipt's `signature_suite` with the new `signature.profile`: not redundant, and a response whose two disagree is rejected. | `core-model.md` §5.1, §5.2, §5.3, §6, §4 response step 4a · `crypto-suites.md` §3 · P-003 §4.2, §6 · P-012 §4, §5 · P-001 issue 12 |
| **E-33** | **`spec/` enumerates Tiers A and B; the registry keeps Tier C.** New `core-model.md` **§5.2.1**: `malformed`, `unsupported_version`, `unsupported_suite`, `routing_mismatch` and `expired` are distinct because each describes the *request*; `unauthenticated` collapses the whole of authentication, since distinguishing an unknown key from a bad signature would let a requester probe which identities a custodian holds; Tier C stays the responder's pinned registry's declared value — manifest-level, so it is in hand for the rejections that never resolve an entry: a replay at step 9, a rate limit at 9a, an unknown predicate at 10. An unrecognised value is an **opaque rejection**, so adding one later does not break an older requester. | `core-model.md` §5.2, §5.2.1 · P-009 §4.1, §5, §3 · P-012 §5, §6 · P-001 issue 12 |
| **E-34** | **One new value, `structurally_invalid`** — a sixth Tier A value for a message that parses and is wrong in a way that is neither a parse failure nor an authentication one: a header carrying `alg`, or one whose `suite` or `key_id` disagrees with the payload's. Not `unsupported_suite` or `unauthenticated`, because the suite was acceptable and nothing failed to authenticate — the `alg` case is refused at step 3 before a signature is checked at all; not `malformed`, because those parse. One value for three causes because which part disagreed is visible in the message the requester itself produced — unlike `unsupported_suite`, which collapses to withhold the custodian's floor. §5.2.1 now states the test a future value must pass: it must send a requester somewhere a neighbouring value would not. | `core-model.md` §5.2.1 · `crypto-suites.md` §3 · P-003 §4.2, §6 · P-009 §4.1, §5 · P-001 issue 13 |
| **E-35** | **A lettered query step 5a**, immediately after parsing: confirm the protected header's `suite` and `key_id` equal the payload's copies. It cannot precede step 5, since it needs the parsed object, and it precedes every step that acts on a payload field. Symmetric with the response order's 4a, which E-32 added for the same check — the requirement had existed in `crypto-suites.md` §3 and P-003 §4.2 with no slot in the query order that cites it. Lettered so steps 6–19 do not renumber. | `core-model.md` §4 query order, §5.2.1 · `crypto-suites.md` §3 · P-003 §4.2, §6 · `conformance-classes.md` CC-2 · `mvp-scope.md` · P-010 · P-001 §5, issue 14 · both schemas and both served copies |

## E-36 — Does §2.2's timestamp spelling bind every string, or only the fields §2.2 names?

**Raised by:** P-002 issue 2, building the production serializer. **Found by:**
Codex, reviewing the Rust and Go implementations of a rule
[`tools/author_vectors.py`](../tools/author_vectors.py) has had since E-23.

### Context

E-23 settled the spelling: uppercase `T`, uppercase `Z`, second precision, one
spelling for every timestamp in the protocol, stated in
[`core-model.md`](../spec/core-model.md) §2.2. What it did not state is the
*reach* — which strings the rule applies to.

The authoring tool resolved that by implementing it, and P-002 issue 2 copied
the tool into Rust and Go, because a serializer that disagrees with the tool
generating the corpus's expected bytes is worse than one that disagrees with the
other implementation. So all three now apply two rules:

- **By name, at protocol level.** A field called `issued_at`, `expires_at` or
  `decided_at` in the core object, `routing`, or a receipt must hold §2.2's
  timestamp. This one is not in question: §2.2 names the fields and §2.2 names
  those three places.
- **By shape, at any depth.** *Any* string carrying some RFC 3339 spelling that
  is not §2.2's is refused wherever it appears — including inside
  `public_context`, which §2.6 says is operation-defined and may mean anything
  at all.

The second rule is not in `spec/`. It is in a tool, and now in two
implementations, and it is the kind of thing an implementer building only from
`spec/` would not produce.

### Concretely

A restaurant predicate's `public_context` carries a booking time, and the
requester writes it the way every other system it talks to writes it:

```json
"public_context": {"booked_for": "2026-07-31T19:30:00+01:00"}
```

That is valid RFC 3339, it is not §2.2's spelling, and it is not a field §2.2
names. Today all three implementations refuse to serialize the query at all. The
requester cannot ask the question, and the failure names a spelling rule for a
field the specification does not claim.

The offset is the interesting part: `+01:00` carries information a `Z` spelling
does not — the local time the diner is thinking in. Normalising it to UTC loses
that, so *"just rewrite it as §2.2's spelling"* is not a lossless workaround.

### Why the shape rule exists at all

It is not arbitrary. Without it, the by-name rule catches only three field names,
and the failure it exists to prevent is a **malformed timestamp inside a signed
payload**, where it is past the reach of anything that reads the payload as
text. A predicate that puts a timestamp in `public_context` under a name §2.2
does not list — `valid_until`, `as_of`, `booked_for` — is then unprotected, and
that is most predicates.

So both rules are defensible and they are in tension. That is the definition of
a spec ambiguity with more than one resolution, which is why this is here rather
than in a commit.

### Options

**A. Keep the shape rule, and state it in §2.2.** The rule is what the corpus
generator has always done; this makes `spec/` say so. Cost: Q2D cannot carry an
offset timestamp as operation-defined data anywhere, and §2.6's *"may mean
anything at all"* acquires an exception it does not currently mention.

**B. Restrict both rules to protocol level, and state that in §2.2.** A field
inside `public_context` is the predicate's, exactly as §2.6 says. Cost: a
predicate's own timestamp fields are unchecked, so a malformed one can be signed
— and a predicate that names its field `expires_at` inside `public_context`
would be checked while one that names it `booked_for` would not, which is a
distinction with no principle behind it.

**C. Restrict to protocol level, and make it the registry's job.** §2.6 data is
validated by the entry's `input_schema` (`scope.md` §4.1), which already has
`format: date-time` available to it. A predicate that wants §2.2's spelling for
its own field says so in its schema; one that wants an offset says that instead.
Cost: `format` is an annotation in JSON Schema, not an assertion, so §4.1 would
need to require it be enforced — a change to the frozen profile, and E-30's
reasoning about libraries disagreeing applies to `format` at least as much as to
`multipleOf`.

### Recommendation — C, falling back to B

**C is the only option that puts the decision where the data's meaning is
already defined.** §2.6 says `public_context` is operation-defined, and
`scope.md` §4.1 already makes the entry's schema the thing that constrains it.
A timestamp in a predicate's public context is predicate data; the predicate's
author knows whether an offset is meaningful and the protocol does not. Under C
a booking predicate declares `format: date-time` and accepts the offset; an
audit predicate declares the §2.2 spelling by pattern and refuses it. Neither
needs `core-model.md` to have an opinion.

C also removes an asymmetry nothing can justify: today, whether a predicate's
timestamp is checked depends on whether its author happened to choose one of
three field names.

**B is the fallback** because it is correct about the boundary even though it
leaves predicate timestamps unchecked. If `format` cannot be made assertive
without reopening §4.1's profile — and E-30 is a real precedent that it might
not be — then B states the honest rule (§2.2 binds the fields §2.2 names) and
leaves predicate data to a later mechanism, rather than pretending the
serializer is that mechanism.

**A is defensible and I do not recommend it.** It is the status quo, it is the
safest against malformed signed timestamps, and it is the least work. But it
makes the protocol refuse valid data on the strength of a rule that is nowhere
in `spec/`, and the reason it is nowhere is that nobody decided it — a tool did.

### Where the recommendation stops being right

**If a predicate's `public_context` is ever compared byte-for-byte across
implementations for a purpose other than the signature** — a digest that some
other party recomputes, say — then C is wrong and A is right, because under C
two predicates can admit two spellings of the same instant and the bytes differ.
Nothing does that today: §4 step 8's byte comparison is over `routing`, whose
fields are all protocol-level, which is exactly what E-23 was for.

**If it turns out that most predicates carry timestamps and few authors write
tight schemas**, C is a rule nobody follows and B's honest gap becomes a real
one. That is an argument for revisiting when the registry has more than three
entries, not for choosing A now — A forecloses the offset case permanently, and
widening later is always available.

### What is built today, pending the decision

**Option B's behaviour: §2.2 binds the fields §2.2 names, and no more.**

That is not a decision — it is the absence of one. The shape rule was in
`tools/author_vectors.py` and in a test asserting it, and P-002 issue 2 copied
it into Rust and Go on the reasoning that a serializer disagreeing with the
corpus generator is worse than one disagreeing with its counterpart. Both
implementations then enforced a rule that is nowhere in `spec/`, which meant an
implementer building only from `spec/` would accept messages ours refuse. Three
implementations agreeing on a rule the specification does not contain is not
cross-implementation agreement; it is three copies of the same unrecorded
choice.

So all three now implement what §2.2 states, and E-36 decides whether to add
more. Restoring the shape rule under option A is one line in each of the three
serializers and one case in each of the three refusal suites.

**No authored vector changed**, which is the check that this narrowing costs
nothing today: `author_message.py --check`, `author_suite.py --check` and
`author_ordering.py --check` all still match, and both `testdata/` fixtures
still serialize byte-identically in all three languages. Nothing in the corpus
carries an RFC 3339 string outside a §2.2 field, so the rule that was removed
had no vector exercising it — which is itself part of why it went unnoticed.

**The rule lived in five places**, and looking found three: the tool, Rust, and
Go. The fourth was `test_authoring.py`'s
`test_the_shape_rule_still_reaches_everywhere`, found by running the suite. The
fifth was `conformance/harness/lint.py`, found by grepping for the predicate
after the other four were done. That is the failure mode
[CLAUDE.md](../CLAUDE.md)'s *Closing an escalation* section describes — a rule
living in more places than the person changing it remembered — arriving on an
escalation being *opened* rather than closed.

**The fifth is deliberately unchanged**, and the reason is a distinction worth
recording: `lint.py` checks **authored vectors**, which are ours. A serializer
produces bytes somebody signs, so refusing by shape stops a requester sending
§2.6 data the specification permits; a linter refusing by shape costs no
requester anything and catches an authoring slip. Same rule, different subject.
If this closes as B or C *and* a vector then needs an offset timestamp under
`expect.output`, that is where to relax it — with the vector as the reason.

---

## E-37 — Does an integer in a signed structure have a range?

**Raised by:** P-002 issue 2. **Found by:** Codex, reviewing the value models.

### Context

[P-002](prds/P-002-message-envelope.md) §4.2 says *"integers — no exponent, no
leading `+`, no leading zeros"* and states no range.
[`core-model.md`](../spec/core-model.md) states none either. So the accepted
domain is whatever each producer's integer type is, and the three producers
disagree: `src/value.rs` and `value.go` both hold a signed 64-bit integer, and
Python's `int` is arbitrary-precision.

That is not a style difference. `tools/author_vectors.py` produces the corpus's
expected bytes, so an unbounded tool can author a vector neither implementation
can reproduce — and the first sign would be a byte disagreement blamed on the
implementations rather than on the vector.

### Concretely

Nothing in the protocol approaches the boundary. Every integer Q2D carries today
is a count, a cardinality, or a capacity in integer millibits — §3.1's unit, and
the largest capacity in the reference manifest is four figures. The gap is
structural rather than live.

But `public_context` is operation-defined (§2.6), and `scope.md` §4.1's schema
profile bounds a *string*'s length and an *array*'s size without bounding an
integer's magnitude. A predicate could register an entry admitting one, and
nothing in the repository would object until two implementations produced
different bytes.

### Options

**A. `core-model.md` states the range: a signed 64-bit integer.** One sentence,
and every producer's accepted domain becomes the same by specification rather
than by coincidence. Cost: a wire-format constraint chosen for an implementation
convenience — 64 bits is what Rust and Go reach for, not something the protocol
needs.

**B. `scope.md` §4.1 bounds it, as it already bounds strings and arrays.** The
constraint lands where the other boundedness rules are, and applies to registry
data — which is the only place an unbounded integer can arrive. Cost: it leaves
protocol fields unbounded, which is fine today because every one of them is a
count, and is the same "fine today" that E-36 turned out to be built on.

**C. Neither: leave it, and treat 64-bit as an implementation detail.** Cost:
the tool has to be bounded anyway, or it can author unreproducible vectors — so
this option still ships the constraint, just without recording why.

### Recommendation — B

**§4.1 already exists to make registry data bounded**, and gives the reason: a
predicate must not be able to register an entry that admits an unbounded
release. An integer's magnitude is the one dimension it currently misses, and
E-28 established the shape of the argument — the entry's schema is what bounds
what a predicate can carry.

B also keeps `core-model.md` free of a number chosen because two languages have
that type. The protocol's own integers are counts and capacities; if one ever
needs a range, the field can state its own, which is what a specification
normally does.

**A is the fallback** if it turns out that protocol fields need the bound too —
but that would be an argument about a specific field, and it should be made
about that field rather than pre-emptively about all of them.

### Where the recommendation stops being right

**If a predicate ever needs an integer larger than 64 bits** — a nanosecond
epoch is 2^61 and would fit, but a hash treated as a number would not — then B
is a bound the registry cannot honestly enforce and the right answer is to say
so in `question_notes` and register a string, as E-30 decided for decimals. That
precedent is close enough that B may be a special case of it.

### What is built today, pending the decision

The tool refuses an integer outside the signed 64-bit range, so it cannot author
what the pair cannot serialize. That is the safe direction under every option —
C included, since C still needs it — and it constrains no vector that exists.
Both implementations are unchanged: their types already are the bound.

---

### What did not change, deliberately

- **`paper/src/manuscript.md` is untouched.** It is the input `make repro`
  rebuilds Draft 0.2.1 from and diffs against the published DOCX; editing it
  would break the check that makes the deposit verifiable. Divergences are
  tracked in [`versioning.md`](versioning.md) and applied in one pass when a new
  draft is opened.
- **The deposited source packages are untouched**, and must stay so. They carry
  a DOI.
- **`core-model.md` §9 stays parked** on the approval-scope digest field list,
  grant lifetime, capacity for `object` outputs, timing and padding, and which
  identity profile is mandatory. E-10 narrowed the identity row rather than
  closing it, and E-02 settled multiplicity without settling lifetime.
