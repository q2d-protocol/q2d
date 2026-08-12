# P-001 — Conformance corpus format and harness contract

| Field | Detail |
|---|---|
| PRD | P-001 |
| Stage | 0 — precedes all implementation code |
| Status | **Ready for decomposition** |
| Size | M |
| Risk | low |
| Blocks | P-002, P-003, P-004, P-005, P-006, P-007, P-008, P-009, P-010, P-011, P-012, P-013, P-014, P-015, P-016 — every other PRD |
| Depends on | nothing |

---

## 1. Purpose

Define the shared test corpus and the contract by which a language-agnostic
harness runs it against any implementation. Every later PRD states its acceptance
as *"both implementations pass corpus section X"*, so this PRD determines what
that sentence means.

Building the corpus first is not sequencing preference. It is the only order in
which cross-implementation divergence is caught as it appears rather than
accumulated. It is also the cheapest available review of the specification: a
requirement that cannot generate a vector is not precise enough to implement, and
we would rather learn that here than in two languages.

**Claims served:** none directly. This PRD builds the instrument by which
Q2D-C-01 through Q2D-C-13 are demonstrated, and by which
[`spec/claims.md`](../../spec/claims.md)'s `Verified by: planned` entries are
closed.

## 2. Spec citations

Requirements this PRD implements, by identifier. It restates none of them.

| Source | What it constrains here |
|---|---|
| [`spec/conformance-classes.md`](../../spec/conformance-classes.md) § *What a conformance suite must provide* | The corpus's required contents |
| [`spec/conformance-classes.md`](../../spec/conformance-classes.md) § *The honesty rule* | No class may be claimed until its checks pass |
| [`spec/claims.md`](../../spec/claims.md) § *Traceability* | Every claim maps to at least one executable check |
| [`spec/core-model.md`](../../spec/core-model.md) §2.1 | Envelope structure the message vectors exercise |
| [`spec/core-model.md`](../../spec/core-model.md) §3.1 | Capacity arithmetic the budget vectors exercise |
| [`spec/core-model.md`](../../spec/core-model.md) §4 | Processing order the ordering vectors exercise |
| [`spec/core-model.md`](../../spec/core-model.md) §5.2 | Normalized denial the rejection vectors exercise |
| [`spec/crypto-suites.md`](../../spec/crypto-suites.md) §3 | `eddsa-jws-2026`, the only suite vectors may use |
| [`spec/crypto-suites.md`](../../spec/crypto-suites.md) §4 | Downgrade rejection the suite vectors exercise |
| [`registry/manifest.json`](../../registry/manifest.json) | Existing predicate vectors, folded in as a corpus section |

## 3. Module boundary

**Inside:** the vector file format; the operation vocabulary; the runner CLI
contract; the harness; the result format; cross-verification mode; coverage
reporting; test key material.

**Explicitly outside:** any protocol logic. The harness parses JSON, invokes a
subprocess, and compares. It implements no Q2D behaviour, and a change that gives
it protocol knowledge is out of scope and an escalation.

**Also outside:** timing and side-channel measurement (Stage 8), performance
benchmarking (Stage 8), and fuzzing corpora (owned by the PRD for the module
being fuzzed).

## 4. Design

### 4.1 The runner contract

An implementation exposes one executable:

```
q2d-conform <vector-file.json>        →  result JSON on stdout
```

Exit status reports whether the runner *functioned*, never whether the vector
*passed*:

| Exit | Meaning |
|---|---|
| 0 | A result was written to stdout. The vector may still fail; the harness decides. This includes a result whose `outcome` is `error`. |
| 1 | The runner could not process the vector — unknown operation, malformed file. No result is written. |
| 2 | A fault so early that no result could be written at all. |

A vector expecting a rejection is a successful run that reports a rejection.
Conflating "the implementation rejected the input" with "the runner failed" makes
negative acceptance untestable, and negative acceptance is where this protocol
lives.

**The dividing line is whether a result was written, not whether anything went
wrong.** `outcome: "error"` is the structured way to say the implementation
faulted on a vector it understood; that is a result, so it is exit 0 and the
harness reports it. Exit 2 is the case where nothing could be written — the
runner crashed, or could not reach stdout. Both fail the vector; the difference
is whether the harness has anything to say about why, and stating it here rather
than leaving each runner to choose is what keeps two implementations from
disagreeing about process status before they can disagree about anything
interesting.

### 4.2 Implementations never see the expectation

**The harness strips `expect` before writing the file the runner reads.**

An implementation that can read the expected output can pass by reproducing it.
This is not a hypothetical: a runner written to make a suite green will, given
the answer, use it. The corpus is only evidence if the implementation is answering
the question rather than copying the answer.

Consequence: vectors are authored as one file containing both halves, and the
harness produces the input-only projection at runtime. Implementations are never
given a path to the authored corpus.

Two properties of that projection, decided here rather than left in the harness:

- It is built from the **allowlist** §6 fixes — `id`, `operation`, `input` —
  rather than by deleting `expect`. A deletion keeps this section true only for
  the fields someone thought of; a later `expected` or `notes_for_the_runner`
  passes straight through one. An allowlist excludes a new authored field by
  default rather than by memory.
- Its **member order is fixed**. §6 fixes what a runner receives, not how it is
  serialized, so this is a harness decision and not a §6 requirement: two runs
  must write byte-identical projection files, or a runner that digests its input
  sees a difference the corpus did not intend.

### 4.3 Determinism is required, not hoped for

Every input that would otherwise vary is supplied **by the vector**: keys,
nonces, `issued_at`, `expires_at`, and any identifier. A runner that generates a
nonce or reads a clock produces an unreproducible result and is non-conforming.

Ed25519 signing is deterministic (RFC 8032), so two conforming implementations
produce **byte-identical** signatures for the same key and message. That is what
makes cross-implementation comparison a byte comparison rather than a
both-verify check, and it is the property the Stage 1 gate rests on.

### 4.4 Vector format

```json
{
  "id": "message/sign/query-minimal",
  "section": "message",
  "requirement": ["Q2D-C-05", "core-model.md#2.1"],
  "description": "A minimal signed query envelope. The output is the compact serialization itself — see the bytes rule below.",
  "operation": "sign_query",
  "input": { "key_id": "test-requester-1", "query": { } },
  "expect": {
    "outcome": "ok",
    "output": "eyJhbGciOiJFZERTQSIsImtp…",
    "comparison": "bytes"
  }
}
```

- `requirement` is mandatory and is what makes the corpus a live traceability
  matrix. A vector citing nothing is rejected by the linter.
- `comparison` is `bytes` where the spec requires determinism and `semantic`
  where it does not. A vector must state which; there is no default, because a
  silent default is how a determinism requirement gets quietly dropped.

**A `bytes` comparison is exact over a string and impossible over an object.**
The harness parses JSON, so what it can compare is what survives parsing. For a
string value — a JWS compact serialization, a digest, a signature — that is
exact: the artefact *is* the string, and `"\u003c"` and `"<"` carry the same
one. For an object or array the bytes never reached the harness at all:
whitespace between tokens and the choice of escape are gone before any
comparison sees them, and re-serializing the parsed tree would assert a byte
equality nobody checked.

So **a value compared as `bytes` must be a string** — the serialization itself.
`cross` refuses to call a `bytes` vector agreed when its `output` or
`rejection.wire` is composite on *both* sides: it reports `UNCHECKABLE` and
fails the run. **Everything else about that vector is still compared** — as a
tree, which is all the format left — because two implementations can reject for
different internal reasons behind byte-identical denials, and reporting only
"the harness cannot see the bytes" would bury exactly the divergence a
normalized denial is designed to hide from a requester. `UNCHECKABLE` is
therefore the verdict only when everything visible agreed, and the report says
so. One side reporting a string and the other a
structure is a different thing and is reported as a divergence: the two runners
disagree on the shape of the answer, and the non-string side did not produce the
artefact at all. Calling that a format limitation would hide an implementation
divergence behind a corpus note. `step` and `internal_reason` are exempt: neither crosses the
interface, so their encoding is nobody's contract.

That rule is satisfiable today for `output`, which is why the example above
carries a compact serialization. **It is not satisfiable for a denial's wire
response, and that is §10's question.** `rejection.wire` is an object in both
the vector and the result format, so the harness cannot check that two
rejections in a normalized class are byte-identical — which is what
[P-009](P-009-denial-normalization.md) requires of them. Those vectors are
`UNCHECKABLE` in `cross` by design until the format changes; the finding is
that the requirement is currently asserted by documents and by no check, not
that the corpus is missing coverage it could have. The cross-vector assertion
over *authored* vectors still compares their wire objects with authored key
order preserved, which catches field order and content — that is the corpus
agreeing with itself, and it is not the same as two implementations agreeing
on bytes.

**`semantic` is defined as parse-then-deep-equal**, and only that:

- both sides are parsed as JSON and compared as trees — object key order is
  irrelevant, array order is **significant**, and numbers compare by parsed
  value rather than by lexical form;
- **absent and null are different.** A field missing from one side and null on
  the other is a mismatch, because the two mean different things in every
  structure this protocol defines;
- no coercion of any kind: no string-to-number, no case folding, no whitespace
  normalization inside string values.

Array order is significant because every ordered thing in Q2D is
security-relevant — `permitted_sinks` and `authorities_consulted` are sets whose
serialized order must still be reproducible across two implementations, and a
comparison that ignored order would hide exactly the iteration-order divergence
[CLAUDE.md](../../CLAUDE.md) forbids.

`semantic` applies to **unsigned** material only — `routing`, and harness-level
structures. Anything inside `signed` compares as `bytes`, because the signature
covers exact transmitted bytes ([`core-model.md`](../../spec/core-model.md)
§2.1) and a semantic comparison there would accept two byte strings that cannot
both verify. That answers [P-002](P-002-message-envelope.md)'s question about
`routing`: yes, `semantic`, and only because it is outside the signature.

**Where the two modes actually differ is `cross`, not `run`.** §4.8 states the
byte comparison as a cross-implementation assertion — *for every
`comparison: bytes` vector, both runners produce identical bytes* — and that is
the only place transmitted bytes exist to compare. Against an authored
expectation the harness has parsed the runner's JSON, and once parsed, object
key order and a number's lexical form are gone; what survives is every string,
which is what the specification requires determinism over — a JWS compact
serialization, a digest, a signature. So `run` compares both modes as
parse-then-deep-equal, `cross` holds `bytes` vectors to identical output, and
the declaration is what tells `cross` which vectors those are.

Four smaller decisions the format carries, recorded here because
[`conformance/vector.schema.json`](../../conformance/vector.schema.json) should
not be the only place they exist:

- **`expect.outcome` is `ok` or `rejected`.** `error` is the third value a
  *runner* may report (§6) and means the runner faulted. A vector never expects
  it: an internal error is not a passing result, and a corpus able to expect one
  could green-light a runner that had stopped working.
- **`section` is a closed vocabulary**, extended additively by the PRD that owns
  the new section — the same discipline §4.5 applies to operations, for the
  smaller reason that a typo must not silently create a section that `coverage`
  then reports on.
- **A `requirement` entry is a claim identifier, a conformance class, or a
  `file.md#section` citation**, and the linter checks that each resolves: a
  claim in [`claims.md`](../../spec/claims.md), a class in
  [`conformance-classes.md`](../../spec/conformance-classes.md), or a numbered
  section of a document in `spec/` **or `threat-model/`** — a vector may
  exercise something the threat model names rather than the specification. The
  cited *section* must exist, not merely the file: a citation pointing at
  nothing is worse than no citation, because it reads as traceability to anyone
  who does not re-derive it.
- **A vector's `section`, the first segment of its `id`, and the directory it
  sits in must agree.** Three statements of one fact, so a mis-filed vector is
  caught by the two that disagree rather than found when a section-scoped run
  quietly omits it.

### 4.5 Operation vocabulary

Closed and versioned. An unknown operation is exit 1, never a skip — fail-closed
applies to the harness too.

| Operation | Stage | Purpose |
|---|---|---|
| `sign_query` / `sign_response` | 1 | Produce a signed envelope |
| `verify_query` / `verify_response` | 1 | Verify, then report the parsed object |
| `digest` | 1 | Digest a structure, for receipt binding |
| `resolve_predicate` | 2 | Registry resolution and pinning |
| `effective_domain` | 2 | Domain narrowing composition |
| `capacity_debit` | 3 | Millibit debit for an effective domain |
| `policy_decide` | 3 | Policy contract input → decision + modifiers |
| `evaluate_predicate` | 4 | Local evaluation and output validation |
| `process_query` | 4 | The full §4 pipeline |

Later stages extend the table; they do not redefine existing entries.

**Stages 5–8 need operations this table does not have, and the extension must be
one coordinated change rather than four.** Each later PRD arrived at its own
needs independently, and an operation named `http_exchange` in one
implementation and `binding_exchange` in the other is a divergence the corpus
exists to prevent — with the added hazard that it would surface as a runner
error rather than as a failing vector.

| Anticipated operation | Stage | Needed by |
|---|---|---|
| `build_contract` | 5 | [P-012](P-012-requester-runtime.md) `requester/contract/` |
| `project_outcome` | 5 | [P-012](P-012-requester-runtime.md) `requester/outcome/`, `requester/projection/` |
| `retry_bytes` | 5 | [P-012](P-012-requester-runtime.md) `requester/retry/` |
| `http_exchange` | 6 | [P-013](P-013-https-binding.md) `binding/`, open question 5 there |
| `fingerprint` | 6 | [P-014](P-014-identity-pairing.md) `identity/fingerprint/` |
| `resolve_identity`, `verify_delegation` | 6 | [P-014](P-014-identity-pairing.md) `identity/` |
| `escalate_poll`, `approve` | 7 | [P-015](P-015-escalation-lifecycle.md) `escalation/` |

Names are proposals, not decisions — the point of listing them together is that
they are settled once, here, before either implementation writes a runner.

Two entries have moved since this table was written, and settling the vocabulary
must account for both:

- **`http_exchange` no longer needs a registry-entry path.**
  `GET /predicates/{id}/{version}` was dropped from Stage 6
  ([P-013](P-013-https-binding.md) §4.3), so no vector exercises it.
- **A sequence-asserting operation is needed at Stage 5.**
  [`core-model.md`](../../spec/core-model.md) §4.1 makes the requester's response
  processing order normative, and [P-012](P-012-requester-runtime.md)'s
  `requester/order/` has to assert *which step rejected*, not merely that the
  response was rejected. `ordering/` does this responder-side today; the same
  shape is needed on the requester side.

[P-015](P-015-escalation-lifecycle.md) needs a **minimal timing capability at
Stage 7** — an assertion that two response paths fall within a band, so that an
opaque escalation can be shown not to be distinguishable by latency. Open
question 3 is resolved that way: the capability moves to Stage 7, full timing
bands and measurement stay at Stage 8 with
[P-016](P-016-demonstration-adversarial.md).

### 4.6 Result format

```json
{
  "vector_id": "message/sign/query-minimal",
  "outcome": "ok",
  "output": { },
  "implementation": { "name": "q2d-rs", "version": "0.1.0" }
}
```

A rejection reports **both halves**, because the harness checks both:

```json
{
  "vector_id": "registry/reject/unknown-predicate-version",
  "outcome": "rejected",
  "rejection": {
    "internal_reason": "unknown_predicate_version",
    "wire": { "status": "deny", "external_reason": "unavailable" },
    "step": 10
  }
}
```

`step` is the [`core-model.md`](../../spec/core-model.md) §4 step at which
rejection occurred, and is how ordering is asserted without instrumenting the
implementation. **It is a field of a conformance result, not of any Q2D
message** — nothing on the wire carries it, and
[`core-model.md`](../../spec/core-model.md) §4 defines the order it names
without defining this field. Its shape and its optionality are therefore this
PRD's to fix, and are fixed here.

**It is an integer for a numbered step and a string for a lettered one.** §4's
table carries **step 9a**, the rate-limit check, and the example above shows an
integer only because the vector it is drawn from rejects at step 10. A format
that could not name 9a would force a conforming runner to misreport where it
rejected — and 9a is precisely the step whose ordering matters, since a limiter
running after registry resolution would leave unknown predicates unlimited and
become the existence oracle [`core-model.md`](../../spec/core-model.md) §9.1
introduced it to avoid.

### 4.7 The harness

Written in **Python**, and it imports neither implementation.

Sharing code with an implementation would let the harness share a bug with it —
a canonicalization or digest error present in both would cancel out and the suite
would pass. A third language makes that impossible by construction, and Python is
already in use for [`registry/validate.py`](../../registry/validate.py).

Modes:

```sh
harness run      --impl ./target/debug/q2d-conform      # one implementation
harness cross    --a <runner> --b <runner>              # two runners, one corpus
harness coverage                                        # claims with no vector
harness lint                                             # corpus self-checks
```

### 4.8 What the harness asserts

**Per vector:** outcome matches; output matches under the declared comparison
mode; for rejections, the internal reason, the wire response, and the step all
match.

The step is optional on a vector (§4.6), so "matches" needs saying precisely:
**where a vector states a step, the runner's must equal it; where a vector
states none, it asserts nothing about the step** and a runner may still report
one. A vector that cares about ordering says so, which is what `ordering/` is;
one that does not is testing something else and should not fail on a field it
never claimed.

**Cross-vector** — the assertions a per-vector test structurally cannot make:

1. **Denial uniformity.** Every rejection in a normalized class produces a
   byte-identical `wire` object, while distinct `internal_reason` values exist
   behind it. This is the check `registry/validate.py` already performs over
   registry vectors, generalized.
2. **Budget accumulation is order-independent.** A debit sequence and its
   permutations reach the same total.
3. **Ordering monotonicity.** No vector rejecting at step *n* has a sibling that
   reaches a later step on strictly less valid input.

The first two are implemented in
[`conformance/harness/cross_vector.py`](../../conformance/harness/cross_vector.py).
**The third is not, and the reason is that it is not yet checkable.** "Strictly
less valid input" is a relation *between* two vectors, and nothing in the format
expresses it: the harness cannot tell that one vector is a weakened form of
another rather than a different case entirely, and a check that guessed would
either pass everything or fail correct pairs. Making it real needs vectors to
declare the relation — a format change, and therefore a decision rather than an
implementation detail. Until then it is a stated assertion with no check, and
saying so beats an implementation that appears to enforce it.

Two smaller decisions the implemented pair carry:

- **Denial uniformity groups by the external class a vector's own wire response
  declares**, not by section. Grouping by section would be wrong in both
  directions: §4.1's Tier A causes share a section and are *deliberately*
  distinct, and one normalized class spans sections.
- **A contradiction fails; an incompleteness reports.** Two causes under one
  external class disagreeing on the bytes is a corpus contradicting itself, and
  fails. A class with only one cause behind it is *reported*, because the
  harness cannot tell it from a Tier A error:
  [P-009](P-009-denial-normalization.md) §4.1's Tier A rejections are
  deliberately distinct from one another — a malformed envelope and an unknown
  version tell a requester different things on purpose — so each is one cause
  under one external value, and nothing in the vector format says which external
  values name a *normalized* class. A rule that failed every single-cause class
  would reject a correct corpus for containing the tier that exists to be
  informative. The same treatment covers a debit sequence with no permutation to
  compare against.
- **The wire comparison does not sort keys.** Two responses carrying the same
  fields in a different order are different bytes on the wire, and normalising
  that away before comparing would remove the thing being checked. Python's
  parser preserves the order keys appeared in, so authored order survives into
  the comparison.

**Cross-implementation:** for every `comparison: bytes` vector, both runners
produce identical bytes; and in `cross` mode, B verifies what A produced.

Issue 9 built the first half. Four decisions it needed, recorded here because
each is a property of the corpus rather than of one mode's code:

- **What is compared is the result's values, field by field — not the two
  runners' stdout.** Every result carries an `implementation` naming who
  produced it, so comparing whole documents would report every vector as
  divergent. The envelope's own key order and whitespace are excluded for the
  same reason: whether a runner writes `outcome` before `vector_id` is a
  property of its JSON writer, not of Q2D.
- **Key order inside a runner-produced object is *not* compared, by either
  mode**, and that is a gap rather than a decision. `semantic` ignores object
  key order by definition (§4.4), and `bytes` refuses a composite value
  outright, so there is no path on which two runners emitting the same fields
  in a different order are reported as divergent. On the wire those are
  different bytes. It is the same gap as the one §10 raises for denials and
  closes the same way — a serialization the harness can compare as a string.
- **A result carrying the wrong `vector_id` is not an answer.** The comparison
  drops `vector_id` deliberately, so without an explicit check two runners that
  both returned the same canned result for some other vector would be reported
  as agreeing across the whole corpus. The mode that has two runners to be
  wrong at once needs that check more than `run` does, not less.
- **A divergence that needs no byte comparison is reported before the question
  of whether the bytes are comparable is asked.** Two runners reaching
  different outcomes, or reporting different fields, have diverged whatever the
  encoding — and a rejection's wire response is an object, so asking about
  comparability first would file the clearest divergence there is under the
  format's limits.
- **`outcome: "error"` is not an answer.** It is the contract's way of saying
  the runner faulted internally, a vector cannot expect one (§4.6 admits `ok`
  and `rejected` only), and the only field two errors share is the word
  `error`. Comparing them would report agreement for a vector on which neither
  implementation produced anything, so it counts as no answer given, exactly
  like exit 1.
- **One runner answering and the other not is a divergence; neither answering
  is not.** Asymmetry is the two of them disagreeing — one language implements
  this vector and the other does not — and scoring it as merely unusable would
  let a `bytes` vector implemented on one side pass this mode in silence, which
  is the coverage gap the Stage 1 gate exists to close. When *neither* answers,
  neither has claimed anything, so there is nothing they disagree about;
  judging either against the corpus is `run`'s job.
- **A partial corpus fails.** A file that will not parse, or a vector that does
  not conform to the schema, is one neither runner was asked about — so
  agreement *across the corpus* has not been shown. Printing that beside a zero
  exit would make a partial run look like a complete one. The two are counted
  and named apart, because a non-conforming vector is the corpus being wrong
  and an unusable pair is the runners being wrong.
- **Two runners agreeing about nothing is not agreement**, so it *fails*. An
  empty corpus, or one neither runner can answer, exits non-zero saying which
  in words rather than printing `0/0 agree`. `run` does the same over an empty
  corpus, for the same reason: a gate that exits 0 having compared nothing
  reports the property holding on the days it was never tested. `lint` still
  exits 0 there — "every vector here is well-formed" is true of none, where
  "these implementations agree" is not.
- **The second half — feeding what A signed into B's verification — is issue
  19, not part of issue 9, and cannot be done from inside the harness as
  scoped.** It requires knowing which operation consumes a signed envelope and
  under which input field, which is P-002's and P-003's knowledge; §3 puts
  protocol logic outside the harness explicitly. Making it real needs a vector
  to declare its companion, which is a format change. Until then `cross` says
  on every run — including a clean one — that it compared what each runner
  produced and did not put A's output to B — **and exits 2 rather than 0 when
  the runners agree**, because the exit status is the only part of the report a
  CI gate reads, and every sentence above it could be perfect while the status
  still said the clause holds. 2 is distinct from 1: 1 means the two runners
  disagreed, 2 means they did not and the mode still cannot establish what §4.8
  asks. If §10's open question is decided the other way, this becomes 0 and the
  reason line stays.

**Coverage:** every claim in [`spec/claims.md`](../../spec/claims.md) is cited by
at least one vector. Uncited claims are reported, not silently absent.

### 4.9 Test key material

Fixed Ed25519 keypairs, generated once, committed, and marked test-only in the
filename and in a header comment. Seeds from RFC 8032's test vectors where they
fit, so key handling is checkable against an independently published source
before any Q2D structure is involved.

## 5. Corpus sections at completion of Stage 0

| Section | Vectors | New work |
|---|---|---|
| `message/` | envelope construction, signing, verification, routing projection, routing/signed disagreement | new |
| `suite/` | suite resolution, downgrade rejection, unknown suite | new |
| `replay/` | nonce reuse, expiry, clock skew, idempotent retry | new |
| `registry/` | resolution, pinning, digest mismatch, schema validation | **folded in from [`registry/manifest.json`](../../registry/manifest.json)** |
| `domain/` | narrowing, understatement, expansion attempt | new |
| `budget/` | debit sequences, permutation equality, exhaustion | new |
| `receipt/` | field binding, digest computation | new |
| `ordering/` | one vector per rejection step, 1–15 | new |

Stage 0 authors the format, the harness, and `message/`, `suite/`, and
`ordering/`. Remaining sections are authored by the PRD that owns the behaviour,
against this format.

## 6. Interfaces

Language-neutral. Both implementations honour these; idiom is per-language.

```
run(vector: VectorInput) -> Result
  VectorInput  = { id, operation, input }        // no expect field
  Result       = { vector_id, outcome, output?, rejection?, implementation }
  outcome      = "ok" | "rejected" | "error"
  rejection    = { internal_reason, wire, step? }
```

## 7. Acceptance

- [ ] The harness runs, and reports **fail for every vector**, because no
      implementation exists. A harness that cannot fail is not a harness.
- [ ] `harness lint` rejects a vector with no `requirement`, no `comparison`, or
      an unknown `operation`.
- [ ] `harness coverage` reports all 13 claims as uncovered.
- [ ] The input projection given to a runner provably contains no `expect` field.
- [ ] Existing registry vectors run through the harness with unchanged results.
- [ ] The harness imports neither implementation — asserted by dependency check,
      not by convention.

## 8. Negative acceptance

What must fail, and how the failure is observed.

| Must fail | Observed as |
|---|---|
| A runner that reads a clock or generates a nonce | Two runs of the same vector produce different output; harness reports non-determinism. **Every vector runs twice for this reason** — nothing else catches it, and the byte comparison the Stage 1 gate rests on would fail later for reasons nobody could place |
| A runner that emits exit 1 for a vector expecting rejection | Harness reports runner failure, distinct from vector failure |
| A vector asserting an outcome it does not cite a requirement for | `harness lint` rejects it |
| A vector with `comparison` unset | `harness lint` rejects it |
| Two rejections in one normalized class with differing `wire` objects | Cross-vector denial-uniformity assertion fails |
| A budget permutation reaching a different total | Cross-vector accumulation assertion fails |
| A `bytes` vector where two implementations differ by one byte | Cross-implementation comparison fails, naming the offset |
| A `bytes` vector whose compared value is an object rather than a string | `harness cross` reports it `UNCHECKABLE` and fails — the bytes never reached the harness, so calling it agreement would assert what was never checked |
| A corpus where the two runners agree on everything comparable | `harness cross` still exits non-zero — §4.8's second clause is issue 19, and the exit status must not say a half-checked clause holds |

The last row is the one this PRD exists for.

## 9. Escalate-if-changed decisions

Each is architecture, not preference. A contributor encountering a reason to
change one stops and escalates.

1. **Implementations never receive the `expect` field.** Changing this makes the
   corpus unfalsifiable.
2. **The harness imports neither implementation.** Shared code means shared bugs
   that cancel out.
3. **All nondeterministic inputs come from the vector.** No clocks, no RNG, no
   ambient state.
4. **The implementation reports; the harness judges.** An implementation that
   decides its own pass/fail can diverge in its reading of the expectation.
5. **Byte comparison depends on Ed25519 determinism.** A future suite without it
   requires a different comparison model, and that is a spec-level change.

## 10. Open questions

| Question | Belongs to |
|---|---|
| ~~How are unsigned parts of a message compared when JSON key order is unconstrained?~~ | **Resolved: `semantic` is parse-then-deep-equal**, with array order significant, absent ≠ null, and no coercion. It applies to unsigned material only; anything inside `signed` compares as `bytes`. §4.4 carries the definition |
| ~~Does the corpus version independently of the spec, or track it?~~ | **Resolved: it tracks the spec.** The corpus exists to demonstrate that a spec version is implementable, so a vector set that could drift from the version it tests would let two implementations agree with each other and with neither spec. A corpus release is identified by the `spec/vX.Y` it was authored against ([`versioning.md`](../versioning.md)) |
| ~~Should `process_query` vectors carry expected timing bands?~~ | **Resolved: a minimal timing capability is pulled forward to Stage 7.** Not a measurement framework — an assertion that two response paths fall within a band, which is what [P-015](P-015-escalation-lifecycle.md) issue 4 needs to show an opaque escalation is not distinguishable by latency. Full timing bands stay at Stage 8, where [P-016](P-016-demonstration-adversarial.md) owns measurement and reporting |
| ~~**The §4.5 operation-vocabulary extension for Stages 5–8.**~~ | **Resolved: settled as one change, before Stage 5** — issue 17, not an open question. §4.5 now lists every anticipated operation with its owning PRD, and no later PRD names one unilaterally: four PRDs choosing separately would diverge at the *runner* level, where it surfaces as an unknown-operation error rather than a failing vector. The list already reflects the two decisions that changed it — the registry-entry endpoint is gone, and `requester/order/` needs an operation that can assert *which step* rejected |
| **Does `cross` satisfy §4.8's cross-implementation clause with only the first half built?** Issue 9 compares what two runners each produced; putting A's signed output to B for verification needs a vector to name its companion artefact and the field that consumes it — a format change, and protocol knowledge §3 places outside the harness. I split it to issue 19, made every run state which half it did, and **held `cross` to exiting 2 even when the runners agree**, so nothing can read the clause off its status. **The scope reduction is Peter's call, not mine**, and until it is made this is fail-closed: the mode does not return success for a clause it half-checked. Deciding it either way is a one-line change — approve the split and agreement returns 0, or reject it and issue 9 stays open until issue 19 lands with it | **Raised, awaiting decision.** Recorded here rather than settled in the PRD, because narrowing an acceptance clause is a scope decision even when the honesty of the output is preserved |
| **Should a runner report a wire response as its serialized string rather than as a parsed object?** As formatted, `rejection.wire` is an object, so the bytes are gone before the harness sees them: it can compare fields, content, and authored key order, but not whitespace or escaping. That means neither `cross` nor the denial-uniformity assertion can establish the byte-identity [P-009](P-009-denial-normalization.md) requires of a normalized class — they establish structural identity, which is weaker and reads the same in a report. My recommendation is that a runner reports the response *both* ways: the serialization as a string for the byte comparison, and the parsed object for the structural checks that need to reach inside it. The cost is a format change and a second field every runner must fill; the alternative is that Q2D's byte-identity requirement is asserted by documents and never by a check | **Raised, awaiting decision.** A format change, and it changes what P-009's vectors can demonstrate |
| ~~Where do fuzzing seeds live — corpus or per-module?~~ | **Resolved: per-module.** The corpus is the cross-implementation contract and every file in it must mean the same thing to both runners; a seed corpus is a local artifact of one fuzzer's coverage history and would make the shared corpus non-reproducible between languages. Seeds live beside the fuzz target that produced them |

## 11. Issues

Decomposition into tracked work. Each names its acceptance.

| # | Issue | Done when |
|---|---|---|
| 1 | Vector file schema and JSON Schema for it | `harness lint` validates a corpus directory against it |
| 2 | Input-projection: strip `expect` | Property test proves no projection contains the key |
| 3 | Runner CLI contract document + reference stub in Python | Stub runs, returns `error` for every operation, harness reports fail-all |
| 4 | Harness `run` mode | Executes a corpus against a runner, reports per-vector pass/fail |
| 5 | Harness `lint` mode | Rejects the four malformed-vector cases in §8 |
| 6 | Harness `coverage` mode | Reports all 13 claims uncovered against an empty corpus |
| 7 | Cross-vector assertions: denial uniformity | Generalizes `registry/validate.py`'s check to any corpus section |
| 8 | Cross-vector assertions: budget order-independence | Permutation test over a debit sequence |
| 9 | Harness `cross` mode | **Half built, and stays open.** Two runners over one corpus, compared field by field, reporting the first differing byte offset — and exiting 2 rather than 0 when they agree, because §4.8's B-verifies-A half is not done. Whether that half becomes issue 19 or stays inside this issue is §10's open question; until it is decided, this issue is not closable |
| 10 | Test key material | Fixed keypairs committed, RFC 8032 seeds where applicable, marked test-only |
| 11 | Fold `registry/` vectors into the corpus | Registry vectors run under the harness with unchanged results |
| 12 | Author `message/` section | Envelope, signing, verification, routing disagreement |
| 13 | Author `suite/` section | Resolution, downgrade rejection, unknown suite |
| 14 | Author `ordering/` section | One vector per rejection step 1–15 |
| 15 | Dependency assertion: harness imports no implementation | CI check fails if either is importable from the harness |
| 16 | `semantic` comparison implemented per §4.4 | Array order significant; absent ≠ null; no coercion; both runners agree on a differing-tree report |
| 17 | **Settle the §4.5 operation vocabulary for Stages 5–8, as one change** | Every operation named, with its owning PRD; no later PRD introduces one unilaterally. Closes after the endpoint drop and the requester-order addition, both already reflected in §4.5 |
| 18 | Minimal timing capability, available at Stage 7 | A vector can assert two response paths fall within a band; [P-015](P-015-escalation-lifecycle.md) issue 4 can be written against it |
| 19 | **Cross-verification: put A's output to B** | *Proposed, not yet approved — see §10.* §4.8's second cross-implementation clause, which issue 9 found needs a vector to name its companion artefact and the field that consumes it — a format change, and protocol knowledge §3 places outside the harness. Blocked on [P-002](P-002-message-envelope.md) and [P-003](P-003-crypto-suites.md) settling which operation consumes a signed envelope |

Issue 16 blocks 12 — `message/` cannot be authored until `semantic` behaves
identically in both runners. Issue 17 blocks the corpus sections of
[P-012](P-012-requester-runtime.md) … [P-015](P-015-escalation-lifecycle.md) —
four PRDs naming their own operations would diverge at the *runner* level, which
surfaces as an unknown-operation error rather than a failing vector: the one
failure the corpus cannot catch, because the corpus is what is broken. Issue 1
blocks everything else.
