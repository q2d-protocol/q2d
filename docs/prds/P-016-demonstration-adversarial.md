# P-016 — Reference demonstration and adversarial suite

| Field | Detail |
|---|---|
| PRD | P-016 |
| Stage | 8 — closes MVP |
| Status | **Blocked on escalation** — open question 1 |
| Size | M |
| Risk | low to build; **the publication surface is the project's largest overstatement risk** |
| Depends on | P-001 … P-015 — everything |
| Blocks | nothing |

---

## 1. Purpose

Produce the artifacts an outsider uses to run the protocol, attack it, and check
the measurements — and report what those attempts and measurements actually
show.

Every prior PRD builds something. This one publishes, and publication is where
[`CLAUDE.md`](../../CLAUDE.md)'s standing warning applies most directly:
overstatement is frictionless and costs most. The demo script, the measurement
report, and the quickstart will be read by people deciding whether to trust the
protocol, most of whom will never read `spec/`.

**Claims served.** None. [`mvp-scope.md`](../mvp-scope.md) §4 lists no claim for
this stage, correctly — a suite of attacks that fail is not a claim, and §4.1 is
about why.

What this PRD does own is the moment
[`claims.md`](../../spec/claims.md)'s `Verified by: planned` entries either close
or are shown not to have closed (§4.6).

## 2. Spec citations

| Source | What it constrains here |
|---|---|
| [`spec/claims.md`](../../spec/claims.md) § *Traceability* | Every claim maps to an executable check; a claim with no passing test is a design intention |
| [`spec/claims.md`](../../spec/claims.md) Q2D-NC-05 | Timing, size, notification, rate-limit, and state channels remain |
| [`spec/claims.md`](../../spec/claims.md) Q2D-NC-06, Q2D-NC-07 | A compromised executor is not defended against; capacity is not severity |
| [`spec/claims.md`](../../spec/claims.md) Q2D-NC-12 | No novelty claim; the contribution is the composition |
| [`spec/conformance-classes.md`](../../spec/conformance-classes.md) § *The honesty rule* | A class is claimed only when every check for it passes |
| [`spec/crypto-suites.md`](../../spec/crypto-suites.md) §7 | Semantic answer size reported separately from total wire bytes |
| [`spec/terminology.md`](../../spec/terminology.md) §9 | The controlled claim vocabulary every published artifact must obey |
| [`threat-model/trust-matrix.md`](../../threat-model/trust-matrix.md) §4, §5 | The adversaries to model, and the channels that stay open |
| [`docs/mvp-scope.md`](../mvp-scope.md) §1 | The walkthrough, and the ten attacks an outsider must be able to attempt |
| [`docs/mvp-scope.md`](../mvp-scope.md) §4 | The Stage 8 gate: an outsider reproduces the demo and the measurements |

## 3. Module boundary

**Inside:** the demonstration scenario and its synthetic fixtures; the
adversarial suite; the measurement harness and its reporting; the traceability
matrix; the quickstart, deployment, and operational-security documents; the
reproduction entry point.

**Explicitly outside:** any protocol behaviour. If an attack in §4.2 succeeds,
the fix belongs to the PRD that owns the module, not here — this PRD reports and
does not patch. Timing *normalization*, which
[P-009](P-009-denial-normalization.md) §4.7 owns and which stays off by default.
Any new mechanism at all: a stage that adds behaviour while measuring it has
measured something that was never reviewed.

**Also outside:** the technical report.
`paper/Q2D_..._v0.2.2_Source_Package/` is deposited and immutable. Measurements
from this stage inform a future draft; they do not edit that one.

## 4. Design

### 4.1 What the adversarial suite demonstrates, and what it cannot

Stated first because every artifact this PRD produces has to respect it.

> The suite demonstrates that **ten named attacks, written by the people who
> wrote the implementation, fail against that implementation.**

It does not demonstrate that the protocol is secure, that no other attack
succeeds, or that the implementation is free of defects. It cannot, and no
phrasing makes it. An adversarial suite is strongest evidence about the
attacker's imagination and weakest evidence about everything else, and ours
shares an author with the code it attacks.

The Stage 8 gate compounds this and should be read precisely: an outsider
**reproduces** the demo and the measurements. Reproduction is not independent
review. Someone re-running our attacks and getting our results has confirmed
determinism, not soundness.

Three rules follow, and they bind every artifact:

- The suite is described as **"ten attacks that fail"**, never as a security
  evaluation, an audit, or evidence of absence.
- **Reproduction and review are named separately** wherever the gate is
  described.
- The suite's value is that it makes attack **cheap for someone else** — the
  fixtures, keys, and harness let a stranger try their own attack in an
  afternoon. That is the real deliverable, and it is worth more than any result
  we produce with it.

### 4.2 The ten attacks, each against a claim

[`mvp-scope.md`](../mvp-scope.md) §1 enumerates what an outsider must be able to
attempt without our help. Each maps to a claim it would break, which is what
makes the suite a test rather than a demo.

| # | Attack | Breaks | Defended by |
|---|---|---|---|
| 1 | Answer-domain understatement | Q2D-C-02 | [P-006](P-006-request-validation.md) §4.5 |
| 2 | Capacity-debit forgery | Q2D-C-09 | [P-008](P-008-capacity-accounting.md) §5 — `capacity_for` cannot see the request |
| 3 | Suite downgrade | Q2D-C-05, C-06 | [P-003](P-003-crypto-suites.md) §4.2 |
| 4 | Replay | Q2D-C-07 | [P-004](P-004-replay-idempotency.md) §4.2 |
| 5 | Duplicate debit | Q2D-C-09 | [P-004](P-004-replay-idempotency.md) §4.6 |
| 6 | Purpose substitution | Q2D-C-05 | [P-002](P-002-message-envelope.md) §4.4 — signature coverage |
| 7 | Sink substitution | Q2D-C-05 | Same |
| 8 | Registry-digest substitution | Q2D-C-02 | [P-005](P-005-registry-client.md) §4.5 |
| 9 | Adaptive probing to reconstruct a constraint set | Q2D-C-09 | [P-008](P-008-capacity-accounting.md) §4.3 keying; [`core-model.md`](../../spec/core-model.md) §2.5 |
| 10 | Timing analysis of denial paths | Q2D-C-08 — **and Q2D-NC-05 says it succeeds** | §4.5 |

**Attack 10 is not expected to fail, and the suite must not be built as though
it were.** Q2D-NC-05 states plainly that timing channels remain, and
[P-009](P-009-denial-normalization.md) §4.7 explains why fail-fast ordering makes
step-level differences inherent. Its result is a measurement, reported in §4.5,
not a pass.

Attack 9 is the one whose outcome is genuinely unknown before it runs. It is
also the one whose result is hardest to state honestly, because "we could not
reconstruct the constraint set within the budget" is a statement about our
probing strategy, not about the bound.

Each attack ships as a runnable script with its own fixtures, its expected
result, and the claim it targets — so a reader can change it and see what
happens, which is the point.

### 4.3 Two kinds of reproduction, and they must not be conflated

The gate says an outsider reproduces the demo **and the measurements**. Those are
different acts with different success criteria, and stating one criterion for
both makes the gate unachievable.

| Kind | Covers | Reproduces to |
|---|---|---|
| **Deterministic** | The exchange, signatures, receipts, byte counts, attack outcomes | **Byte-identical.** Fixed keys, nonces, and clock, per [P-001](P-001-conformance-corpus.md) §4.3 |
| **Statistical** | Timing distributions | The stated **conclusion**, within stated bounds — never identical numbers |

Every timing figure is published with method, sample size, hardware, operating
system, load conditions, and variance. A single number with no method is not
reproducible and should not be published as though it were.

The deterministic half uses the same discipline `paper/`'s `make repro` already
applies to the manuscript: a pinned entry point that regenerates the artifact and
diffs it. Consistency here is not tidiness — a reader who has already reproduced
the paper knows what the command means.

### 4.4 Measurement: three numbers, never one

[`crypto-suites.md`](../../spec/crypto-suites.md) §7 requires semantic answer
size to be reported separately from total wire bytes, and
[`mvp-scope.md`](../mvp-scope.md) §4 extends that to three:

| Measure | Is |
|---|---|
| **Source bytes** | What a conventional integration would have transferred to answer the same question |
| **Model-context bytes** | What the caller receives — the projected semantic answer ([P-012](P-012-requester-runtime.md) §4.4) |
| **Total wire bytes** | The whole exchange: envelope, signature, receipt, response |

Reporting only the first two flatters the protocol enormously — a one-bit answer
against a whole calendar record. Reporting only the third hides the point
entirely. **Publishing all three is what makes the comparison honest**, and it
is the number that will look worst — protocol overhead against a one-bit answer —
that a reader most needs in order to evaluate the design. A future post-quantum
suite makes that ratio far worse, which is exactly why §7 requires the
separation.

Two constraints on how these are described:

- **Model-context bytes is not evidence of evidence segregation.**
  [P-012](P-012-requester-runtime.md) §4.8 does not claim Q2D-C-12, CC-10 is not
  built, and there is no model in MVP. The number measures the projection's size
  and nothing about containment.
- **Capacity debited is not a severity measure.** Q2D-NC-07 and
  [`terminology.md`](../../spec/terminology.md) §9 both forbid *"one bit,
  therefore harmless"*. A report placing "1000 millibits" beside a byte count
  must not imply proportionality between them — the demo's own predicate is
  classified `high` sensitivity for a one-bit answer, and that contrast is worth
  showing deliberately rather than leaving a reader to infer the opposite.

### 4.5 Timing: the measurement that will not flatter us

Stage 8 measures denial timing across causes. **The expected result is that Tier
C rejections are distinguishable by latency**, because
[P-009](P-009-denial-normalization.md) §4.7 chose fail-fast ordering
deliberately — a rejection at step 10 completes far sooner than one at step 14,
and checking cheaply before expensively is the right design.

So the measurement will show a real distinction that the wire response does not
carry. [`core-model.md`](../../spec/core-model.md) §4's third invariant — that
the external response must not reveal which step failed — remains true; the
timing reveals it anyway. Q2D-NC-05 and
[`trust-matrix.md`](../../threat-model/trust-matrix.md) §5 already scope this,
but the measurement turns a stated caveat into a number.

**That number gets published.** Both configurations:

| Configuration | Reports |
|---|---|
| Padding hook **off** (default) | The real step-level distribution — what a deployment gets by default |
| Padding hook **on** | What the mechanism costs in latency, and how much distinction it actually removes |

[P-009](P-009-denial-normalization.md) §4.7 built the hook *"so Stage 8 can
measure the difference rather than needing to build the mechanism first"*. This
is that measurement, and the second configuration is not evidence the channel is
closed — padding a response does not address queue delay, rate-limit behaviour,
or notification timing.

Deciding **not** to publish the unflattering configuration is the escalation
here, not deciding to publish it.

### 4.6 The traceability matrix, including the empty rows

[`claims.md`](../../spec/claims.md) § *Traceability* requires every claim to map
to at least one executable check before Phase 1 is described as complete, and
distinguishes a claim with a passing test from a design intention. This is where
`harness coverage` stops reporting all thirteen uncovered.

**At the end of MVP, three claims will still have no passing test:**

| Claim | Why |
|---|---|
| Q2D-C-11 binding equivalence | One binding. Equivalence needs two — [P-013](P-013-https-binding.md) §4.8 |
| Q2D-C-12 evidence segregation | Conditional on `q2d-contained-runtime-0.1`; CC-10 not built — [P-012](P-012-requester-runtime.md) §4.8 |
| Q2D-C-13 flow confinement | Same |

The matrix shows them as **design intentions with no passing test**, in the same
table as the ten that pass, rather than omitting them or footnoting them. A
coverage report that lists only what passed is a marketing document.

The direct consequence: **MVP completion is not Phase 1 completion in
`claims.md`'s own terms**, and no artifact may say it is. Open question 1 asks
whether [`mvp-scope.md`](../mvp-scope.md) §1 should say so explicitly, since
"definition of done" currently reads as though finishing the walkthrough
finishes the phase.

Conformance classes get the same treatment.
[`conformance-classes.md`](../../spec/conformance-classes.md)'s honesty rule
means MVP may state the classes whose checks all pass and must state that CC-8,
CC-9, and CC-10 are not implemented — with CC-12, if it is added
([P-013](P-013-https-binding.md) open question 2), reporting whatever its checks
show.

### 4.7 The demonstration scenario

Two parties, synthetic data, scripted, deterministic. `menu_compatible`, per
[`mvp-scope.md`](../mvp-scope.md) §1 item 3, then a denial, a normalized denial,
budget exhaustion, and an escalation.

**The fixtures are synthetic and must look it.** The predicate's registry entry
classifies dietary exclusions `high` sensitivity with a written rationale about
GDPR Article 9 proxies, so a demo fixture that reads as a plausible real person's
dietary and religious profile is the wrong artifact to publish regardless of its
provenance. Obviously-fictional subjects, and a note in the fixture file saying
so.

The scenario runs both directions — Rust requester against Go custodian and the
reverse — because [`mvp-scope.md`](../mvp-scope.md) §1 item 7 is the item that
matters and a demo that only runs one way does not exercise it.

### 4.8 Operator documentation is a collation, not new material

Every "required configuration with no default" and every manual step already
exists in a prior PRD. The operational-security document collects them; it
invents nothing, and anything in it that cannot be traced to a PRD is a sign
something was decided in a document nobody reviews.

| Must be configured, or the daemon refuses to start | From |
|---|---|
| Pinned registry key and manifest digest | [P-005](P-005-registry-client.md) §4.1 |
| Audit retention period | [P-011](P-011-receipts-audit.md) §4.7 |
| Receipt retention, requester side | [P-012](P-012-requester-runtime.md) §4.7 |
| Suite policy floor | [P-003](P-003-crypto-suites.md) |
| Grant lifetime | [P-015](P-015-escalation-lifecycle.md) §4.6 |
| Key file permissions | [P-014](P-014-identity-pairing.md) §4.6 |

| Manual step nothing can do for the operator | From |
|---|---|
| Comparing pairing fingerprints out of band | [P-014](P-014-identity-pairing.md) §4.3 |
| Reviewing a manifest diff before changing a pin | [P-005](P-005-registry-client.md) §4.3 |
| Revoking a compromised key on every machine | [P-014](P-014-identity-pairing.md) §4.5 |
| Deciding whether escalation is explicit or opaque | [P-009](P-009-denial-normalization.md) §4.6 |

The document also states what the deployment does **not** protect against: a
compromised computation executor (Q2D-NC-06, and
[`trust-matrix.md`](../../threat-model/trust-matrix.md) §4 calls it the single
point of failure), every channel in §5 of that document, and unmediated sinks
(Q2D-NC-11, CC-10 not built).

## 5. Interfaces

Artifacts rather than functions. Each is an executable entry point.

```
demo run                       // the §4.7 scenario, deterministic
demo run --swap                // Rust requester ↔ Go custodian
adversarial run [attack-id]    // one attack or all ten; reports result vs expectation
measure bytes                  // the three §4.4 numbers
measure timing [--padding]     // distributions, with method and variance
harness coverage --matrix      // §4.6, including rows with no passing test
repro                          // regenerates every deterministic artifact and diffs
```

`adversarial run` reports each attack's **expected** outcome alongside its
actual one, so attack 10 succeeding is a pass of the suite and not a failure of
it. A suite in which every attack must fail cannot express a known open channel,
and would either hide attack 10 or misreport it.

`harness coverage --matrix` extends [P-001](P-001-conformance-corpus.md) §4.7's
existing mode rather than adding a tool.

## 6. Corpus sections

This PRD authors no protocol vectors. It consumes every section and adds two
that are about the artifacts rather than the protocol:

| Group | Vectors |
|---|---|
| `demo/` | The §4.7 scenario as a deterministic vector sequence, both directions |
| `adversarial/` | One vector per attack, each citing the claim it targets and its expected outcome |

Both use [P-001](P-001-conformance-corpus.md)'s format, and `adversarial/`
vectors carry `requirement` entries naming the claim — which is what lets
`harness coverage --matrix` count them.

## 7. Acceptance

- [ ] `demo run` produces **byte-identical** output in both implementations, and
      `demo run --swap` completes in both directions.
- [ ] All ten attacks run, and each reports its actual outcome against its
      expected one; attack 10's expected outcome is *succeeds*.
- [ ] `measure bytes` reports all three numbers separately, and no artifact
      reports fewer than three.
- [ ] `measure timing` publishes both padding configurations, with method,
      sample size, hardware, and variance.
- [ ] `harness coverage --matrix` lists all thirteen claims, marking Q2D-C-11,
      C-12, and C-13 as having no passing test.
- [ ] `repro` regenerates every deterministic artifact and diffs clean.
- [ ] An outsider completes the [`mvp-scope.md`](../mvp-scope.md) §1 walkthrough
      and reproduces the deterministic measurements from published artifacts
      alone.
- [ ] Every published artifact passes a [`terminology.md`](../../spec/terminology.md)
      §9 vocabulary check.

The seventh cannot be self-certified, and neither can the eighth be delegated to
grep alone — §9's prohibitions are about meaning, and a sentence can overstate
without using a listed phrase.

## 8. Negative acceptance

| Must fail | Observed as |
|---|---|
| The suite described as a security evaluation, audit, or evidence of absence | Review of every artifact; grep will not catch the paraphrases |
| Reproduction described as independent review | Same — the gate's wording is the risk |
| Attack 10 reported as a pass, or omitted | Suite reports nine attacks, or ten passes |
| Timing published for the padded configuration only | The default configuration's numbers absent |
| Any measurement reported as fewer than three numbers | A single "bytes" figure appears anywhere |
| Model-context bytes cited as evidence of evidence segregation | Q2D-C-12 referenced in a measurement context |
| Capacity debit presented as a severity measure | "Only one bit" framing anywhere — Q2D-NC-07 |
| The coverage matrix omitting claims with no passing test | Fewer than thirteen rows |
| Any artifact describing Phase 1 or MVP as complete in `claims.md`'s terms | Grep plus review |
| A conformance class claimed whose checks do not all pass | The honesty rule |
| Demo fixtures resembling a real person's dietary or religious profile | Review of the fixture files |
| A timing figure published without method and variance | A bare number |
| This stage adding protocol behaviour to make a measurement work | Any diff outside `demo/`, `adversarial/`, and docs |
| The two implementations described as independent | Grep — they share an author |

Row 1 is this PRD's entire risk. It will not arrive as a false statement; it will
arrive as a confident summary sentence at the top of a README, written by someone
pleased that ten attacks failed.

Row 13 matters because the temptation is specific and plausible: a measurement
that needs a hook, an endpoint, or a flag to work, added at the stage where
nothing is reviewed against a claim.

## 9. Escalate-if-changed decisions

1. **The suite is ten attacks that fail, never a security evaluation.**
2. **Reproduction and independent review are named separately.**
3. **Attack 10 is expected to succeed**, and the suite reports it as such.
4. **Timing is published for both configurations**, default first. Withholding
   the unflattering one is the change requiring escalation.
5. **Three numbers, always** — source, model-context, and total wire bytes.
6. **The coverage matrix shows claims with no passing test.**
7. **Nothing describes MVP as Phase 1 complete.**
8. **This stage adds no protocol behaviour.**
9. **Demo fixtures are obviously fictional.**

## 10. Open questions

| Question | Belongs to |
|---|---|
| **1.** [`mvp-scope.md`](../mvp-scope.md) §1's "definition of done" reads as though completing the walkthrough completes the phase, but three claims will have no passing test (§4.6). Proposed: state in §1 that MVP completion is not Phase 1 completion in [`claims.md`](../../spec/claims.md)'s terms, and name the three | Escalation — a `mvp-scope.md` wording change with public consequences |
| **2.** [P-015](P-015-escalation-lifecycle.md) issue 4 needs a timing assertion at **Stage 7**, but [P-001](P-001-conformance-corpus.md) §10 deferred timing to Stage 8 on the assumption nothing earlier would need it. Proposed: pull a minimal timing capability forward into the harness; this PRD still owns measurement and reporting | [P-001](P-001-conformance-corpus.md); a sequencing correction |
| **3.** Does attack 9 have a defined stopping condition, or does it run until the budget is exhausted? Proposed: budget exhaustion, with the reconstruction achieved reported as a fraction — an open-ended probe produces a result nobody can reproduce | This PRD; blocks issue 4 |
| **4.** Where do measurements live — a repository document, or a future draft of the report? Proposed: the repository, versioned with the code that produced them; the deposited report is immutable and a future draft cites the repository | This PRD |
| **5.** Should the adversarial suite ship with a template for contributing a **new** attack? Proposed: yes. Making a stranger's attack cheap is §4.1's real deliverable, and a template is most of that | This PRD |
| **6.** Does the demo need a failure mode where an attack **succeeds** against a deliberately misconfigured deployment — no fingerprint check, TOFU pairing enabled? Proposed: yes, as the clearest way to show what the manual steps are actually for | This PRD |

## 11. Issues

| # | Issue | Done when |
|---|---|---|
| 1 | Synthetic fixtures, obviously fictional | Fixture files reviewed; no plausible real profile |
| 2 | `demo run` and `demo run --swap` | Byte-identical in both; both directions complete |
| 3 | Attacks 1–8 as runnable scripts | Each reports actual against expected; each cites its claim |
| 4 | Attack 9, adaptive probing | Stopping condition defined (open question 3); reconstruction reported as a fraction |
| 5 | Attack 10, timing analysis | Reported as *succeeds*; feeds issue 7 |
| 6 | `measure bytes` | Three numbers; no path emits fewer |
| 7 | `measure timing`, both configurations | Method, sample size, hardware, variance published; default configuration first |
| 8 | `harness coverage --matrix` | Thirteen rows; three marked as having no passing test |
| 9 | `repro` entry point | Regenerates and diffs clean; mirrors `paper/`'s discipline |
| 10 | Quickstart | An outsider completes the walkthrough from it alone |
| 11 | Deployment and operational-security document | Every §4.8 row traced to a PRD; non-protections stated |
| 12 | Misconfiguration demonstration | Open question 6; an attack succeeds where a manual step was skipped |
| 13 | New-attack template | Open question 5; a stranger adds an attack without reading this PRD |
| 14 | Claim-language audit across every published artifact | §9's prohibitions checked by review, not only grep |
| 15 | Outsider runs the gate | Someone who did not write any of it reproduces the demo and the deterministic measurements |

Issue 15 is the stage gate and the MVP gate, and it is the only issue in this
repository that cannot be completed by the people who wrote it. Issue 14 should
run immediately before it, because the artifacts an outsider reads first are the
ones least reviewed against `spec/`.
