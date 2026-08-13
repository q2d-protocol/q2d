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
> **E-27 is the only one open.** It blocks
> [P-006](prds/P-006-request-validation.md) issue 4's `enum` half, and it is a
> live disagreement between `spec/` and
> [`registry/validate.py`](../registry/validate.py) rather than a question with
> no answer yet. All sixteen PRDs remain Ready for decomposition.
>
> **E-26 closed**, and gave `core-model.md` a new **§3.3**: two narrowings of one
> dimension compose to their greatest lower bound. Where that bound is a range no
> value satisfies, the domain is empty and fails closed — correcting §3's claim
> that narrowing alone cannot reach an empty domain. Where it is an empty
> `allowed_detail_fields`, §3.3 rejects it **as an interim rule** and says so,
> because whether an object release with no detail fields is admissible is the
> same question **E-27** is deciding for `enum`.
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
| **E-27** | Is a release that cannot vary with the data admissible — a one-label `enum`, an empty field set? | E-25's cascade | `core-model.md` §2.5, §3.2 · `registry/validate.py` | **Open** |
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
`{ac, bd}` are both admissible under §3.2's four conditions and neither factors
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

One caveat, and it belongs to **E-27** rather than here: if that question
resolves toward admitting a one-label coarsening, every table gains a `"1": 0`
key, and every entry carrying one is re-authored. That cost is E-27's whichever
way E-25 had gone — B does not create it and A would not have avoided it — but
"no migration at all" was too strong, and it is zero today only because no entry
carries a table.

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
**Decides** [`core-model.md`](../spec/core-model.md) §2.5 and §3.2, and
[`registry/validate.py`](../registry/validate.py) ·
**Blocks** [P-006](prds/P-006-request-validation.md) issue 4's `enum` half —
`check_narrowing` *is* the condition list, so building it decides whether there
are four conditions or five. The `object` route to the same release is not
blocked: §3.3 states an interim rule for it, where §3.2's four conditions already
admit the `enum` case and amending them would be the decision itself. Nothing
else waits on this; no registry entry carries a capacity table yet. It is a **standing disagreement between documents** rather
than merely an undecided question, and it silently determines a debit.

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

**The same shape reaches it by a second route, and one answer has to cover
both.** §2.5 permits `answer_contract.allowed_detail_fields` to be **empty**, and
E-26's §3.3 composes two disjoint field sets to exactly that. An `object` answer
with no detail fields is the same thing a one-label `enum` coarsening is: a
release that cannot vary with the data, at a cardinality of one and a debit of
zero. Whatever E-27 decides for the `enum` case should be the same answer for the
`object` case, or the spec forbids a constant by one route and permits it by
another. §3.3 rejects an empty effective allowlist as an
interim rule and marks it as one, in the way §3.2 carried an interim `enum` rule
until E-25 — so an implementation has determinate behaviour meanwhile and nothing
has been settled by the back door.

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

### Recommendation — A

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
into an escalation or a denial instead. Worth asking whether P-016's adversarial
work needs one before this is closed.

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
| **E-26** | **The greatest lower bound**, per dimension: the coarser value where the dimension is a number or a duration, and the **intersection** where it is a range or a field set, which are ordered by containment and so need not be comparable. Where the bound is a range no value satisfies, the domain is empty and fails closed; where it is an empty `allowed_detail_fields`, §3.3 rejects it as an interim rule pending E-27, which is deciding the same question for `enum`. `enum` cannot arise, which is what keeps the rule total. Raised naming three incomparable shapes; `interval` granularity was not one of them — it is a duration, and durations are ranked. | `core-model.md` §3 and §3.3 (new) · `terminology.md` §6 · P-006 §4.1, §5, §6, issue 6 · P-007 §4.4, §5, §10, issue 4 |

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
