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
  "description": "A minimal signed query envelope with an advisory routing projection.",
  "operation": "sign_query",
  "input": { "key_id": "test-requester-1", "query": { } },
  "expect": {
    "outcome": "ok",
    "output": { "signed": "…", "routing": { } },
    "comparison": "bytes"
  }
}
```

- `requirement` is mandatory and is what makes the corpus a live traceability
  matrix. A vector citing nothing is rejected by the linter.
- `comparison` is `bytes` where the spec requires determinism and `semantic`
  where it does not. A vector must state which; there is no default, because a
  silent default is how a determinism requirement gets quietly dropped.

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
harness cross    --a <runner> --b <runner>              # A produces, B verifies
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

**Cross-implementation:** for every `comparison: bytes` vector, both runners
produce identical bytes; and in `cross` mode, B verifies what A produced.

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
| A runner that reads a clock or generates a nonce | Two runs of the same vector produce different output; harness reports non-determinism |
| A runner that emits exit 1 for a vector expecting rejection | Harness reports runner failure, distinct from vector failure |
| A vector asserting an outcome it does not cite a requirement for | `harness lint` rejects it |
| A vector with `comparison` unset | `harness lint` rejects it |
| Two rejections in one normalized class with differing `wire` objects | Cross-vector denial-uniformity assertion fails |
| A budget permutation reaching a different total | Cross-vector accumulation assertion fails |
| A `bytes` vector where two implementations differ by one byte | Cross-implementation comparison fails, naming the offset |

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
| 9 | Harness `cross` mode | A produces, B verifies; reports first differing byte offset |
| 10 | Test key material | Fixed keypairs committed, RFC 8032 seeds where applicable, marked test-only |
| 11 | Fold `registry/` vectors into the corpus | Registry vectors run under the harness with unchanged results |
| 12 | Author `message/` section | Envelope, signing, verification, routing disagreement |
| 13 | Author `suite/` section | Resolution, downgrade rejection, unknown suite |
| 14 | Author `ordering/` section | One vector per rejection step 1–15 |
| 15 | Dependency assertion: harness imports no implementation | CI check fails if either is importable from the harness |
| 16 | `semantic` comparison implemented per §4.4 | Array order significant; absent ≠ null; no coercion; both runners agree on a differing-tree report |
| 17 | **Settle the §4.5 operation vocabulary for Stages 5–8, as one change** | Every operation named, with its owning PRD; no later PRD introduces one unilaterally. Closes after the endpoint drop and the requester-order addition, both already reflected in §4.5 |
| 18 | Minimal timing capability, available at Stage 7 | A vector can assert two response paths fall within a band; [P-015](P-015-escalation-lifecycle.md) issue 4 can be written against it |

Issue 16 blocks 12 — `message/` cannot be authored until `semantic` behaves
identically in both runners. Issue 17 blocks the corpus sections of
[P-012](P-012-requester-runtime.md) … [P-015](P-015-escalation-lifecycle.md) —
four PRDs naming their own operations would diverge at the *runner* level, which
surfaces as an unknown-operation error rather than a failing vector: the one
failure the corpus cannot catch, because the corpus is what is broken. Issue 1
blocks everything else.
