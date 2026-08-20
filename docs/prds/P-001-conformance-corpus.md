# P-001 — Conformance corpus format and harness contract

| Field | Detail |
|---|---|
| PRD | P-001 |
| Stage | 0 — precedes all implementation code |
| Status | **Ready for decomposition** |
| Size | M |
| Risk | low |
| Blocks | P-002, P-003, P-004, P-005, P-006, P-007, P-009, P-010, P-011, P-016 — every other PRD — ~~P-008, P-012, P-013, P-014, P-015~~ **deferred 2026-08-19** |
| Depends on | nothing |


> **Reading this PRD after the 2026-08-19 scope reduction.**
>
> Where the sections below reason about the **disclosure-capacity budget**
> ([`claims.md`](../../spec/claims.md) Q2D-C-09, *not attempted in this release*)
> or the **escalation lifecycle** ([P-015](P-015-escalation-lifecycle.md),
> deferred), that reasoning is **preserved as written and is not a requirement of
> this release**.
>
> **What governs what gets built:** the **issue list**, the **acceptance** and
> **negative-acceptance** tables, and the **corpus-section** table. Struck rows in
> any of those say what does not. Design prose does not govern. Design prose has deliberately *not* been rewritten to
> remove deferred concepts: it records why each decision was made, and deleting
> it would leave the decisions standing with their reasons removed — which is
> worse than a reader having to hold one caveat.
>
> Deferred PRDs keep their numbers and their issue lists. Nothing was withdrawn.

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

**Also outside:** timing and side-channel measurement, performance benchmarking
— both **cut** by the 2026-08-19 reduction rather than deferred to a later stage
— and fuzzing corpora (owned by the PRD for the module
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

#### Configuration is an input

§9 item 3 forbids **ambient state**, and a responder's configuration is ambient
state. Its suite registry and its acceptable set are read from local files, so a
vector that does not supply them asserts a rule against whatever the runner was
built with, and passes or fails for a reason the vector does not state.

Three rules could not be asserted at all until this was written down —
[`crypto-suites.md`](../../spec/crypto-suites.md) §6's `deprecated` and
`withdrawn` verification rules, and
[P-003](P-003-crypto-suites.md) §4.2 step 2's acceptable-set check, which
that PRD's §9 item 1 calls the entire downgrade defence. Each is a property of
the receiver, and nothing in a message can carry it. E-48.

A vector supplies configuration under `input.verifier`:

```json
"input": {
  "verifier": {
    "suite_registry": { "suites": [ … ] },
    "acceptable_suites": ["eddsa-jws-2026"]
  },
  "envelope": { "signed": "eyJ…", "routing": { } }
}
```

Inside `input` rather than beside it. §4.2's projection is an **allowlist** —
`id`, `operation`, `input` — closed on purpose, so that a field nobody
anticipated cannot reach a runner; `input` is copied whole and untouched. A
second top-level block would have spent that closedness to express something
`input` already holds, and would have changed §6's `VectorInput`, the runner
contract and both runners with it.

`verifier` is optional, and each member within it is optional. A vector omitting
one gets the **runner contract's** stated default, not the implementation's
preference — `RUNNER-CONTRACT.md` fixes both, because two runners defaulting
differently make a silent vector mean two things. Most vectors omit it, since
most vectors are about a message rather than about its receiver.

**Configuration is declared; history is replayed.** `verifier` carries state a
responder was *configured into* — the registry it loaded, the suites an operator
wrote down, later a pinned digest. It does not carry state a responder
*accumulated*. A replay cache already holding a nonce ([P-004](P-004-replay-idempotency.md))
or a budget already debited ([P-008](P-008-capacity-accounting.md)) is the outcome
of previous operations, and declaring it would assert the very thing the corpus
exists to demonstrate — a vector could then claim a nonce was seen without any
vector having presented it.

**No mechanism for replayed history exists**, and `verifier` is not it. Those
PRDs need vectors that run in sequence, which the format does not have and this
decision does not add; each must raise it rather than reach for `verifier`
because it is the nearest thing available.

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
| `sign_query` / `sign_response` | 1 | Produce the **`signed` string** — the compact serialization, not the `{signed, routing}` envelope around it. §4.3 makes cross-implementation comparison a *byte* comparison, and a vector cannot assert bytes over an object the harness parses before comparing (§4.4). Assembling the envelope is [P-002](P-002-message-envelope.md)'s `build_envelope`, and `routing` is *derived* by its `project_routing` rather than authored. `verify_query` takes the whole envelope, since §4 step 8 compares the two halves |
| `verify_query` / `verify_response` | 1 | Verify, then report the parsed object |
| `digest` | 1 | Digest a structure, for receipt binding |
| `resolve_predicate` | 2 | Registry resolution and pinning |
| `effective_domain` | 2 | Domain narrowing composition |
| `capacity_debit` | 3 | Millibit debit for an effective domain. **No vector uses it since 2026-08-19** — Q2D-C-09 is not attempted. The name stays in the settled vocabulary rather than being removed: an operation no runner implements is exit 1, which is what §7 expects of unbuilt work, and removing a settled name would reopen the question issue 17 closed |
| `policy_decide` | 3 | Policy contract input → decision + modifiers |
| `evaluate_predicate` | 4 | Local evaluation and output validation |
| `process_query` | 4 | The full §4 pipeline |
| `process_sequence` | 4 | **One responder, several requests, in order** — [E-51](../open-escalations.md). Idempotency is a property of the *second* request and no vector could describe one; the sequence lives inside `input`, where the projection already passes it through untouched, so the vector format, the projection and the runner contract are unchanged. §4.6 fixes what it returns |
| `process_response` | 5 | The requester's §4.1 order, and **which of its steps rejected** — the mirror of `process_query`, for the same reason `ordering/` cannot be assembled from `verify_response` vectors |
| `build_contract` | 5 | [P-012](P-012-requester-runtime.md) `requester/contract/` |
| `project_outcome` | 5 | ~~[P-012](P-012-requester-runtime.md) `requester/outcome/`, `requester/projection/`~~ — **Deferred 2026-08-19** with the contained runtime. Name settled, no vector |
| `retry_bytes` | 5 | ~~[P-012](P-012-requester-runtime.md) `requester/retry/`~~ — **Deferred 2026-08-19**. Name settled, no vector |
| `http_exchange` | 5 | [P-017](P-017-mcp-binding.md) `binding/` — **repointed 2026-08-19**. P-013 is deferred and P-017 reuses the name rather than naming one of its own, which is exactly what settling the vocabulary was for: the MCP binding moves opaque bytes over HTTP, and the harness never speaks MCP any more than it spoke Q2D |
| `fingerprint` | 6 | ~~[P-014](P-014-identity-pairing.md) `identity/fingerprint/`~~ — **Deferred 2026-08-19** with the pairing profile |
| `resolve_identity`, `verify_delegation` | 6 | ~~[P-014](P-014-identity-pairing.md) `identity/`~~ — **Deferred 2026-08-19** |
| `escalate_poll`, `approve` | 7 | [P-015](P-015-escalation-lifecycle.md) `escalation/` |

Later stages extend the table; they do not redefine existing entries.

**The table is settled rather than anticipated**, which is issue 17. It used to
carry the Stage 5–8 names in a second table headed *"names are proposals, not
decisions"*, and the schema's enum deliberately excluded them. Both are now one
list, because the hazard the split was managing is the one it created: an
operation named `http_exchange` in one implementation and `binding_exchange` in
the other is a divergence that surfaces as a runner error rather than as a
failing vector, and four PRDs choosing separately is exactly how that happens.
An operation no runner implements yet is exit 1, which is what §7 already
expects of an unbuilt stage.

Three entries moved while it was being settled:

- **`http_exchange` no longer needs a registry-entry path.**
  `GET /predicates/{id}/{version}` was dropped from Stage 6
  ([P-013](P-013-https-binding.md) §4.3), so no vector exercises it.
- **`process_response` is what the requester-side ordering need was asking
  for.** This section recorded it as *"a sequence-asserting operation"*, which
  was the right need under a word that now means something else:
  [`core-model.md`](../../spec/core-model.md) §4.1 makes the requester's
  response processing order normative, and
  [P-012](P-012-requester-runtime.md)'s `requester/order/` must assert *which
  step* rejected. That is a sequence of **steps** over one response, not a
  sequence of **requests**, which is what E-51 added `process_sequence` for.
  Two different things under one word is how a vocabulary settled to prevent
  divergence causes one, so each now has its own name and the word is not used
  for either.
- **`process_sequence` is new, from [E-51](../open-escalations.md).** It is the
  one entry no PRD proposed here, because the need was raised as an escalation
  rather than as a corpus section.

**One name is deliberately missing.** [P-015](P-015-escalation-lifecycle.md)
needs a **minimal timing capability at Stage 7** — an assertion that two response
paths fall within a band, so that an opaque escalation can be shown not to be
distinguishable by latency. Open question 3 is resolved that way: the capability
moves to Stage 7, full timing bands and measurement stay at Stage 8 with
[P-016](P-016-demonstration-adversarial.md). **What it is called, and whether it
is an operation at all, is issue 18 and is undecided** — so it is absent from
the table and from the enum, and
[`test_vector_schema.py`](../../conformance/tests/test_vector_schema.py) holds
that absence, turning red the day issue 18 lands without the enum being updated.

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
table carries **9a**, the rate-limit check, and **11a**, the registry entry's
non-schema constraints; the example above shows an integer only because the
vector it is drawn from rejects at step 10. A format that could not name them
would force a conforming runner to misreport where it rejected — and both are
steps whose ordering is the point. A limiter running after registry resolution
would leave unknown predicates unlimited and become the existence oracle
[`core-model.md`](../../spec/core-model.md) §9.1 introduced it to avoid; and an
implementation that folded 11a into 11 would satisfy §4 by running a schema
validator and stopping, with no vector able to say which check rejected.

Both are lettered for the same reason, which is worth stating once: §4's numbers
are cited across this repository, so a step inserted mid-sequence is lettered
rather than renumbering everything below it. The **enum is closed** and holds
exactly what §4 defines — a vector naming `12b` would otherwise assert an
ordering the specification does not have.

#### A sequence returns one result, and its outcome is the operation's

`process_sequence` ([E-51](../open-escalations.md)) takes several requests and
one of them may be refused. **The top-level `outcome` stays `ok`**, and the
per-request outcomes are the operation's `output`:

```json
{
  "vector_id": "replay/id-reuse/same-id-different-digest",
  "outcome": "ok",
  "output": {
    "results": [
      { "outcome": "ok", "output": { } },
      { "outcome": "rejected",
        "rejection": { "internal_reason": "query_id_reuse",
                       "wire": { "status": "deny", "external_reason": "unavailable" },
                       "step": 9 } }
    ]
  },
  "implementation": { "name": "q2d-rs", "version": "0.1.0" }
}
```

**`rejected` at the top level would be the wrong statement.** It means the
implementation refused *the input it was given*, and the input here is the
sequence. A responder that answers the first request and refuses the second has
not refused the sequence; it has processed it, and the refusal is what the
sequence was written to show. Reporting it as a top-level rejection would also
lose which request was refused, since `rejection` is one object.

So `result.schema.json` is **unchanged**. Each entry is the operation's data,
under the rule the schema already states about `output` — *"any JSON value; its
shape is the operation's"* — and it is fixed here rather than there for the
reason §4.4 gives for not enumerating per-operation input fields: a schema
listing them would be a second definition of what the owning PRD already fixes.

Two consequences worth stating rather than discovering:

- **The schema does not enforce that an inner rejection carries both halves.**
  The top-level shape does, and this one is compared as data. What holds it is
  the vector's own expectation, which names every field it asserts.
- **`harness cross`'s denial-uniformity check does not walk into `results`.**
  It reads vectors whose *expectation* is a rejection, and a sequence vector's
  is not. That is acceptable because uniformity across causes is `denial/`'s
  section and no sequence vector is in it — but it is a real gap in coverage
  rather than an oversight, and a sequence vector may not be relied on to
  demonstrate uniformity.

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
  fails. **Comparison is pairwise, and each pair is compared on what both of
  them assert** — a projection asserts nothing about what
  it omits, so it does not disagree with a whole response beside it for
  declining to mention two fields. Where every member is whole, they are
  compared whole, so a field present in one and absent in another is the
  divergence it is. That distinction is what lets the first whole-response
  denial vector land beside the `registry/` projections that exist today
  without failing the corpus. Pairwise rather than across the class, because
  intersecting group-wide lets one projection blind it: two vectors asserting
  different receipts would agree because a third omitted `receipt`. **What it compares is named on every run**, because a vector may
  assert a subset of [`core-model.md`](../../spec/core-model.md) §5.2's
  response and the two fields every vector carries today — `status` and
  `external_reason` — are both fixed by the class.

  **A vector asserting a subset is judged on that subset**, in `run` as well as
  in the report. "Asserts nothing about the fields it omits" has to mean
  exactly that, or a conforming implementation returning §5.2's whole response
  fails every `registry/` vector for returning too much — the corpus contract
  and the comparison would disagree, and the comparison would win. It applies
  at the top level of `wire` and nowhere else: **not to `output`**, where an
  answer is bounded by the effective domain and an unasked-for field is the
  failure Q2D-C-03 exists to catch; not inside `receipt`, which is five fields
  or a lint failure; and **only where the vector is
  actually a projection**, decided by what it asserts rather than by which
  section it sits in — one carrying all four of §5.2's fields is asserting the
  whole response wherever it lives, so a fifth field a runner added is a
  divergence from what it asserted, and dropping it would discard the
  cause-specific oracle Q2D-C-08 exists to catch.

- **A receipt a vector does assert is held to §6's shape, and that is an error
  rather than a report.** Omitting `receipt` asserts nothing about it and is
  legitimate; asserting one with four fields or six asserts that a conforming
  implementation emits it, and §6 says *"exactly five fields, and no others"*.
  The extra-field case is the one that matters: a field present for some causes
  and absent for others is the distinction normalization removes, and
  [`claims.md`](../../spec/claims.md) names the concrete instance — *"a denial
  receipt that named the predicate would partition denials by predicate,
  defeating Q2D-C-08"*. Comparing those two compares
  two constants, so a summary that stopped at "one class, five vectors" would
  read as evidence of uniformity while establishing none of it. §5.3 puts the
  leak precisely where the vectors are silent: *"a receipt that recorded
  `escalate` for an outcome the wire made uniform would defeat Q2D-C-08 through
  the evidence attached to it, in the one place nobody looks for a
  normalization leak."* A class with only one cause behind it is *reported*, because the
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
  19, not part of issue 9 (§10, resolved), and cannot be done from inside the
  harness as scoped.** It requires knowing which operation consumes a signed envelope and
  under which input field, which is P-002's and P-003's knowledge; §3 puts
  protocol logic outside the harness explicitly. Making it real needs a vector
  to declare its companion, which is a format change. Until then `cross` says
  on every run — including a clean one — that it compared what each runner
  produced and did not put A's output to B — **and exits 3 rather than 0 when
  the runners agree**, because the exit status is the only part of the report a
  CI gate reads, and every sentence above it could be perfect while the status
  still said the clause holds. The statuses are distinct on purpose: 1 means the
  two runners disagreed or a vector could not be compared, 2 means nothing ran
  at all (bad usage, missing runner, unreadable corpus — the CLI's own code),
  and 3 means they agreed and the mode still cannot establish what §4.8 asks. 3
  becomes 0 when issue 19 lands, and not before.

  **Why the second half is not redundant**, since two runners producing
  identical bytes look as though they must accept each other's output: byte
  agreement compares A's *signer* against B's signer, and says nothing about
  either **verifier**. Signing and verifying are separate code paths, and
  verification is [`core-model.md`](../../spec/core-model.md) §4 step 4, which
  every step from 5 down is gated on — *"nothing below this line runs for an
  unauthenticated request"*. Steps 1 to 3 run before it by design, on envelope
  size and the declared suite; those are the most attacker-exposed lines in the
  protocol and are equally untouched by a signer-to-signer comparison. An
  implementation with a lenient verifier passes every byte-comparison vector in
  the corpus. This is also why issue 19 is
  load-bearing rather than tidy-up: [`mvp-scope.md`](../mvp-scope.md) Stage 1's
  gate **is** cross-verification — *"the Rust implementation verifies signatures
  produced by Go and vice versa"* — and `mvp-scope.md` outranks this PRD.

**Coverage:** every claim in [`spec/claims.md`](../../spec/claims.md) is cited by
at least one vector. Uncited claims are reported, not silently absent.

**Cited is not demonstrated, and the report says so in those words.** A claim
usually rests on more than any one vector shows — Q2D-C-08 needs identical
response size and retry semantics as well as a common external class — so a
count of cited claims would be read as a count of verified ones. `coverage`
says *cited*, per line and in its total, and points at `claims.md`'s **Holds
when** for the rest. `Verified by` in `claims.md` names the specific checks;
this mode is the traceability index, not the verdict.

### 4.9 Test key material

Fixed Ed25519 keypairs, obtained once, committed, and marked test-only in the
filename and **in the file's first field**. Seeds from RFC 8032's test vectors
where they fit, so key handling is checkable against an independently published
source before any Q2D structure is involved.

Two words in that sentence changed when issue 10 built it, and both are
recorded here rather than absorbed quietly.

It said *"generated once"*. Nothing is generated: RFC 8032's vectors fit every
keypair the corpus needs, and generating one would mean generating it *with*
something — a third Ed25519 implementation in the tree. "Obtained once" is the
requirement that was actually meant, and it is the stronger one.

It also said *"in a header comment"*. JSON has no
comments, and the corpus parses strictly (§4.4) — a file carrying a `//` line
would not load. The first field is the same requirement in the format the
material is actually in: the marking is the first thing a reader or a diff
sees. Recorded rather than satisfied quietly, because a test asserting a
first field while the PRD asked for a comment would leave the acceptance
criterion looking met by something else.

They fit for all of them, so none are generated. Three keypairs live in
[`conformance/keys/ed25519-test-only.json`](../../conformance/keys/ed25519-test-only.json),
taken verbatim from RFC 8032 §7.1 TESTs 1–3: two sides of an ordinary exchange,
and a third so a vector can present a signature from the wrong key. The RFC's
own message/signature pairs are committed beside them as reference data — not
as vectors, which is issue 13's work.

Two consequences of using published keys rather than generated ones, both
deliberate:

- **Every private seed here is public.** That is the point — anyone can check
  the values against the RFC — and it is why the marking is in the filename as
  well as the file. A key file is exactly the artefact that gets copied
  somewhere else by someone in a hurry.
- **Nothing in this repository derives a public key from a seed.** Doing so
  would put a third Ed25519 implementation in the tree, in the one place where
  being wrong is invisible: it would agree with whichever implementation shared
  its bug. The check that a keypair is really a keypair comes from RFC 8032
  having published it, and from `known_answers` once a runner exists.

  This one is a **rule, not a check**. No test can decide whether some file
  implements Ed25519 — a hand-rolled one is arithmetic, and a check that tried
  would be pattern-matching against how somebody happened to write it. What is
  checked is narrower and worth stating as such: the harness imports nothing
  outside the standard library (issue 15), so the harness at least cannot reach
  a crypto library. Everywhere else, this holds because it is written down and
  because a reviewer reads the diff.

**No signature over a Q2D structure is committed yet, and nothing prevents one.**
§10 settled *how* one gets authored — [`tools/author_vectors.py`](../../tools/author_vectors.py),
from the specification text rather than from an implementation — and building
that tool found the last thing missing, the JWS protected header's member set,
which is now [`crypto-suites.md`](../../spec/crypto-suites.md) §3. The tool
assembles a signed string; what remains is authoring the vectors, which is
issues 12, 13, and 14.

## 5. Corpus sections at completion of Stage 0

| Section | Vectors | New work |
|---|---|---|
| `message/` | envelope construction, signing, verification, routing projection, routing/signed disagreement | new |
| `suite/` | suite resolution, downgrade rejection, unknown suite | new |
| `replay/` | nonce reuse, expiry, clock skew, idempotent retry | new |
| `registry/` | schema validation, evaluation, normalized denial — **no capacity debit since 2026-08-19** | **folded in from [`registry/manifest.json`](../../registry/manifest.json)** — done, by [`tools/fold_registry.py`](../../tools/fold_registry.py). Resolution, pinning, and digest mismatch are *not* among them: the manifest's vectors exercise a predicate's evaluation and validation, not the act of resolving the entry, so those three remain to author |
| `domain/` | narrowing, understatement, expansion attempt | new |
| ~~`budget/`~~ | ~~debit sequences, permutation equality, exhaustion~~ — **deferred 2026-08-19** with Q2D-C-09. A small `quota/` group belongs with the request quota when it is built | ~~new~~ |
| `receipt/` | field binding, digest computation | new |
| `ordering/` | one vector per rejection step, **1–14** — **not 15**, whose only rejection cause was budget exhaustion and which has none since Q2D-C-09 was marked not attempted (2026-08-20) — **and the lettered steps among them, 5a, 9a and 11a** | new |

Stage 0 authors the format, the harness, and `message/`, `suite/`, and
`ordering/`. Remaining sections are authored by the PRD that owns the behaviour,
against this format.

## 6. Interfaces

Language-neutral. Both implementations honour these; idiom is per-language.

```
run(vector: VectorInput) -> Result
  VectorInput  = { id, operation, input }        // no expect field
                 // input may carry `verifier` — §4.3, and the shape and the
                 // defaults are in conformance/RUNNER-CONTRACT.md
  Result       = { vector_id, outcome, output?, rejection?, implementation }
  outcome      = "ok" | "rejected" | "error"
  rejection    = { internal_reason, wire, step? }
```

## 7. Acceptance

- [ ] The harness runs, and reports **fail for every vector**, because no
      implementation exists. A harness that cannot fail is not a harness.
- [ ] `harness lint` rejects a vector with no `requirement`, no `comparison`, or
      an unknown `operation`.
- [ ] `harness coverage` reports every claim no vector cites. It said *"all 13
      as uncovered"* until issue 11 folded in `registry/`, which took it to
      three; Q2D-C-05 made it four when [E-48](../open-escalations.md) let the
      third of that claim's three named checks be written. The exact set is
      `test_coverage.py`'s `COVERED_TODAY`, which is where it is asserted and
      therefore the only place it should be written down. The criterion was never
      the number — it is that uncited claims are named rather than absent — and
      the number is asserted in the test suite so it cannot drift unremarked.
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
| A denial vector whose receipt records `escalate` behind a uniform wire | `harness lint` rejects it. [`core-model.md`](../../spec/core-model.md) §5.3 names this case outright — it *"would defeat Q2D-C-08 through the evidence attached to it, in the one place nobody looks for a normalization leak"* — so it is the one the `denial/` section most exists to catch |
| An explicit-escalation vector held to a denial's field list | It is not — §5.3's shape is `status: escalate`, `pending_token`, `expires_at`, receipt, signature, and it carries no `external_reason` because it is *"not denial-normalized and must never be described as such"*. An **opaque** escalation is held to §5.2's list, since §5.3 says it returns that same envelope and being indistinguishable is the whole point |
| A `denial/` vector asserting a projection rather than §5.2's whole response | `harness lint` rejects it. Enforced rather than documented: the two fields such a vector would carry are both fixed by the normalized class, so the comparison cannot fail, and a rule with nothing behind it is how a corpus comes to look like it verifies Q2D-C-08 |
| A denial vector whose receipt records `escalate` behind a uniform wire | `harness lint` rejects it. [`core-model.md`](../../spec/core-model.md) §5.3 names this case outright — it *"would defeat Q2D-C-08 through the evidence attached to it, in the one place nobody looks for a normalization leak"* — so it is the one the `denial/` section most exists to catch |
| An explicit-escalation vector held to a denial's field list | It is not — §5.3's shape is `status: escalate`, `pending_token`, `expires_at`, receipt, signature, and it carries no `external_reason` because it is *"not denial-normalized and must never be described as such"*. An **opaque** escalation is held to §5.2's list, since §5.3 says it returns that same envelope and being indistinguishable is the whole point |
| A `denial/` vector asserting a projection rather than §5.2's whole response | `harness lint` rejects it. Enforced rather than documented: the two fields such a vector would carry are both fixed by the normalized class, so the comparison cannot fail, and a rule with nothing behind it is how a corpus comes to look like it verifies Q2D-C-08 |
| A vector whose `expect` carries a timestamp that is not [`core-model.md`](../../spec/core-model.md) §2.2's | `harness lint` rejects it in every case but one, which is stated below rather than papered over. Two mechanisms, because either alone leaves a gap. **By name** — [`core-model.md`](../../spec/core-model.md) §2.2, §5.3 and §6 give `issued_at`, `expires_at` and `decided_at` timestamps, so a malformed one is caught however malformed, including `2026-1-01T00:00:00Z`, which has no RFC 3339 shape to test. **By shape** — anything that looks like a timestamp and is not §2.2's, which reaches a field a later section adds without this list being updated. Neither is a guess at which strings are timestamps. The name rule runs only where the harness structurally knows what it is reading — the rejection's wire response and receipt — and **not** over `expect.output`, whose shape is the operation's (§4.4): a predicate answer may carry an `expires_at` meaning something else, and knowing which one is §2.2's would mean knowing the operation.

  **So state the gap rather than imply it is covered.** Under `expect.output`, only the shape rule runs, and a value malformed enough to have no RFC 3339 shape at all — `2026-1-01T00:00:00Z` — passes lint. Catching that needs to know the field is a timestamp, which needs to know the operation. [`tools/author_vectors.py`](../../tools/author_vectors.py) knows both and refuses it before signing, which is where a `message/` vector's output comes from; a hand-authored one can still carry it, and nothing here would say so. `input` is exempt, because a vector testing that an implementation rejects a bad spelling must contain one. A timestamp inside a *signed* value is out of lint's reach — a compact serialization is one opaque string to a harness that may not know what it contains (§3, module boundary) — so [`tools/author_vectors.py`](../../tools/author_vectors.py)'s serializer refuses the wrong spelling at the last point before it becomes bytes, as it refuses a float. The diagnostic names which rule was missed: a valid RFC 3339 value in another spelling is a different mistake from a value that is no instant, and telling an author the first is "not RFC 3339" sends them to check something that conforms |
| A `denial/` vector whose `wire` carries a value §5.2 or §6 does not give it | `harness lint` rejects it — `status` outside `deny`/`escalate`, an empty string where a value is required, or a `decided_at` that is not RFC 3339 at second precision. The last is not pedantry: §6 grounds the length guarantee in none of the reduced fields being variable-length, and that field is the one that can vary |
| A denial vector asserting a receipt that is not §6's five fields | `harness lint` rejects it — too few or too many. Omitting `receipt` is legitimate and reported as a partial comparison instead |
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
| ~~How are unsigned parts of a message compared when JSON key order is unconstrained?~~ | **Resolved: `semantic` is parse-then-deep-equal**, with array order significant, absent ≠ null, and no coercion. It applies to unsigned material only; anything inside `signed` compares as `bytes`. **`routing` is unsigned and its values still have to match exactly** — [`core-model.md`](../../spec/core-model.md) §4 step 8 requires a responder to compare each projected field against the verified object with no coercion, so a vector asserting a routing projection is asserting values, not shapes. `semantic` delivers that for the fields §2.1 permits there, which are all strings; it would not if one were a number, and §4.4's no-coercion rule is what keeps the two documents saying the same thing. §4.4 carries the definition |
| ~~Does the corpus version independently of the spec, or track it?~~ | **Resolved: it tracks the spec.** The corpus exists to demonstrate that a spec version is implementable, so a vector set that could drift from the version it tests would let two implementations agree with each other and with neither spec. A corpus release is identified by the `spec/vX.Y` it was authored against ([`versioning.md`](../versioning.md)) |
| ~~Should `process_query` vectors carry expected timing bands?~~ | **Resolved: a minimal timing capability is pulled forward to Stage 7.** Not a measurement framework — an assertion that two response paths fall within a band, which is what [P-015](P-015-escalation-lifecycle.md) issue 4 needs to show an opaque escalation is not distinguishable by latency. Full timing bands stay at Stage 8, where [P-016](P-016-demonstration-adversarial.md) owns measurement and reporting |
| ~~**The §4.5 operation-vocabulary extension for Stages 5–8.**~~ | **Resolved, and now done** — issue 17, never an open question. §4.5 is one settled table and the schema enum matches it; four PRDs choosing separately would diverge at the *runner* level, where it surfaces as an unknown-operation error rather than a failing vector. Three things moved in the settling: the registry-entry endpoint is gone, `requester/order/` needs **`process_response`** rather than the thing this row called a sequence-asserting operation, and [E-51](../open-escalations.md) added **`process_sequence`**. Issue 18's timing capability is the one name left out, because it is undecided |
| ~~**Does `cross` satisfy §4.8's cross-implementation clause with only the first half built?**~~ | **Resolved: the split is approved, and the exit status stays non-zero.** Issue 9 closes on byte agreement alone; B-verifying-A is issue 19. `cross` continues to exit 3 rather than 0 when the runners agree, because the exit status is the only part of the report a release gate reads and 0 would let one conclude the clause holds. The two halves are not redundant, which is the reason the second is tracked rather than dropped: byte agreement compares A's *signer* against B's signer and says nothing about either **verifier**, and verification is where [`core-model.md`](../../spec/core-model.md) §4 step 4 gates everything below it. §4.8 and §7 now carry the split |
| ~~**Should a runner report a wire response as its serialized string rather than as a parsed object?**~~ | **Resolved, and the question was the wrong one.** [`core-model.md`](../../spec/core-model.md) §6 settles byte-length uniformity structurally *by design* — the reduced receipt is *"exactly five fields"*, none variable-length, so *"byte-length uniformity across every cause in a normalized class follows from the shape rather than from a check"*. (That argument holds only while every reduced field really is fixed-width, which the timestamp-profile question below puts in doubt: a `decided_at` carrying `+00:00` is six characters where `Z` is one. §6 is the design, not yet a demonstrated property.) The real defect was that **`wire` was undefined**: the schema typed it `{"type": "object"}` while its prose said *"what a requester receives"*, and every vector asserted a two-field fragment of §5.2's four-field response. `vector.schema.json` now defines it — a vector may assert a subset where response construction is not what it tests, and **asserts nothing about the fields it omits**; `denial/` may not, because `status` and `external_reason` are both fixed by the class, so comparing only those compares two constants. The uniformity assertion now names every partial comparison instead of printing a confident summary over a check that could not fail. **Denial vectors become whole-response when the header question below lands** — a response carries a signature — and that dependency is recorded on the header issue itself, not only here |
| ~~**How does a signed vector get authored, when the corpus is what an implementation is checked against?**~~ | **Resolved: from the specification text, by an authoring tool** — [`tools/author_vectors.py`](../../tools/author_vectors.py), written before either implementation exists, kept out of `conformance/harness/` and out of CI's authoring path. Three readings of the specification instead of two, and a disagreement between the tool and either implementation is a specification ambiguity found. Three disciplines carry the decision and are stated in the tool's own docstring: it is **not** described as independent (one author, structural independence only); a tool/implementation disagreement is a **specification ambiguity under investigation**, not an implementation bug, until someone shows which reading the text supports; and its output is committed and thereafter treated as authored data. Its Ed25519 comes from RFC 8032 §5.1 and **the tool refuses to run until it reproduces §7.1's published vectors**, so no constant in it is trusted from memory. Building it immediately surfaced the header gap below |
| ~~**At which step is a registry-entry constraint checked when it cannot be expressed in the entry's input schema?**~~ | **Resolved: a step of its own, `11a`**, immediately after step 11's schema validation ([`core-model.md`](../../spec/core-model.md) §4). Two mechanisms, so two steps: folding them together would let an implementation satisfy §4 by running a schema validator and stopping, and leave an `ordering/` vector unable to say which rejected. Lettered as 9a is, so nothing below renumbers. [P-006](P-006-request-validation.md) already had the distinction — §4.3 separates constraints from schemas and §5 has both functions — so the specification had one step where the module always had two. The folded vector states `11a`, so its `before_private_access` property is machine-checked rather than only described. The lettered-step enum is closed on `9a` and `11a`, in the vector schema and the result schema alike |
| ~~**Which of RFC 3339's spellings may a receipt timestamp use?**~~ | **Resolved: one — uppercase `T`, uppercase `Z`, second precision**, stated once in [`core-model.md`](../../spec/core-model.md) §2.2 for every timestamp in the protocol. The rule already existed in [P-002](P-002-message-envelope.md) §4.2, the only place saying `Z`; relocating it gave it the reach it lacked, since P-002's profile covers the signed payload and **not `routing`** — which §4 step 8 compares against `signed`, now explicitly **byte for byte**. `harness lint` rejects any other spelling per vector, and the corpus-level mixing assertion is gone: with one legal spelling a corpus cannot mix |
| ~~**Is [`core-model.md`](../../spec/core-model.md) §5.2's deny response a closed field list, and where does retry metadata live?**~~ | **Resolved: every §5 response is closed, and retry metadata has nowhere to live.** §5.1 is exactly its listed fields with `evidence` conditional on the assurance profile named in the same response; §5.2 is exactly four; §5.3's explicit escalation exactly five. Adding one is a specification change, on the reasoning §6 already gave for the receipt — a field present for some causes and absent for others reintroduces the distinction normalization removes. It also makes §5.2's *own* size requirement structural: a field set that is not enumerated cannot be size-bounded. **§5.2's retry permission is dropped**: it permitted a field whose only conforming value was uniform, no conformance class allowed the transport form, [P-009](P-009-denial-normalization.md) §4.4 declined to emit any, and a permission with no user is a trap for the next implementer — §9.1 having just made a rate limiter mandatory in every deployment. `harness lint` now rejects an extra response field, where it previously reported one |
| ~~**Which members does the JWS protected header carry?**~~ | **Resolved: `suite` and `key_id`, and no others** — [`crypto-suites.md`](../../spec/crypto-suites.md) §3 now defines the header, and P-003 §4.1 and §4.2 cite it. `suite` carries the *suite identifier*, because P-003 §4.2 step 4 confirms it **equals** the payload's `signature.profile` and an algorithm name could never be equal to one. `key_id` is there because [`core-model.md`](../../spec/core-model.md) §4 resolves the key at step 4 while the payload's `signature.key_id` cannot be read until step 5 — a gap nothing had recorded, found while settling this one. **No `alg`**: a header a general-purpose JOSE library can process is one where that library picks the verification algorithm from unauthenticated data, which is the decision §4's policy check exists to take away from the sender, so `alg: none` is now not a state the format can express rather than a state it rejects. Step 4 also compares the key ids, for the reason it already compared the suites — a producer signing with one key while the header names another verifies fine and disagrees with itself |
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
| 8 | Cross-vector assertions: budget order-independence | **Done — and now inert.** The permutation assertion is built ([`cross_vector.py`](../../conformance/harness/cross_vector.py)) and correct; the `budget/` section it runs over is **deferred 2026-08-19** with Q2D-C-09, so it reports zero groups across zero vectors. Kept rather than removed: it is working code, and it starts asserting again the moment a debit sequence exists |
| 9 | Harness `cross` mode | **Done**, scoped to §4.8's first cross-implementation clause by §10's resolution. Two runners over one corpus, compared field by field, reporting the first differing byte offset — and exiting 3 rather than 0 when they agree, because the B-verifies-A half is issue 19 and a release gate reads the status, not the prose |
| 10 | Test key material | **Done.** Three keypairs from RFC 8032 §7.1 committed in `conformance/keys/`, marked test-only in the filename and the first field, with the RFC's published signatures beside them as reference data. No seed appears outside that directory, asserted by a byte search over every file. That nothing derives a public key from a seed is a rule rather than a check — see §4.9 for why a test cannot decide it, and what is checked instead |
| 11 | Fold `registry/` vectors into the corpus | **Folded; the acceptance cannot close yet.** All fourteen manifest vectors are in the corpus and pass `harness lint`, *generated* from the manifest by [`tools/fold_registry.py`](../../tools/fold_registry.py) rather than transcribed — the manifest outranks the corpus, so it stays the one place they live, and `--check` fails the build on any divergence. What is not shown is *"unchanged results"*: that means a runner reproducing each expected answer, and no runner evaluates `evaluate_predicate` — against the reference stub all fourteen fail, which is the expected state and not the acceptance. This closes when Stage 1 provides a runner. Five of them raised the step question in §10, and five more the bytes question |
| 12 | Author `message/` section | **Done — the six vectors this issue owed.** The section holds twenty-seven now: [P-002](P-002-message-envelope.md) §6 authored `serialize/`, `envelope/`, `digest/` and `reject/` into the same directory and the same tool. Generated by [`tools/author_message.py`](../../tools/author_message.py) with a `--check` in the suite: `sign/query-minimal` asserting the compact string byte for byte, `verify/query-valid`, `routing/subset`, and three rejections — `verify/wrong-signer`, `routing/disagrees`, `routing/introduces-field`. The rejections were blocked until [E-33](../open-escalations.md) enumerated the `external_reason` vocabulary in [`core-model.md`](../../spec/core-model.md) §5.2.1. `routing/disagrees` cites **Q2D-C-05**, which is `conformance/routing-mismatch` under that claim's *Verified by*. It did not at first: the third of the three named checks, `conformance/suite-downgrade`, could not be written until [E-48](../open-escalations.md), and citing a claim from two of its three checks reports it covered on the strength of the parts that were easy |
| 13 | Author `suite/` section | **Done — nineteen vectors.** From [`tools/author_suite.py`](../../tools/author_suite.py): a valid verification, construction under a second key, a tampered payload, header and signature, an unresolvable key, an unregistered suite at step 3, and `downgrade/`'s three structural failures — an `alg`-carrying header at step 3, and a header/payload suite and key mismatch, all three `structurally_invalid` after [E-34](../open-escalations.md). The two mismatch vectors assert step **5a**, which [E-35](../open-escalations.md) added to §4's query order for the comparison — it needs the parsed payload so it cannot precede step 5, and it precedes every step that acts on a payload field. The last three arrived with [E-48](../open-escalations.md): `suite/status/`'s two and the below-floor downgrade all state a fact about the **verifier** rather than about a message, and `input.verifier` (§4.3) is what let them. This row previously said they wait on a *second registered suite*, which was the wrong diagnosis twice over — with one registered there would still have been no way to write *this verifier lists it as withdrawn*, and a suite registered purely to be deprecated is refused as unimplemented before its status is read. `suite/rfc8032/` is no longer waiting on this issue at all — P-003 §6 **retired** it rather than extend §4.5's vocabulary for a raw signature, since the known answers are already gated three ways. [`test_suite_section.py`](../../conformance/tests/test_suite_section.py) holds the `rfc8032/` retirement as an asserted absence, and holds the three suite refusals to one `external_reason` between them — the mapping rather than indistinguishability, since these vectors project two fields and whole-response uniformity is `denial/`'s |
| 14 | Author `ordering/` section | **Six vectors landed — steps 1, 3, 4, 5, 5a and 6 — and the section stops there for a reason stronger than a missing fixture.** A vector asserting rejection at step N must **pass** steps 1 to N-1, so a request that cannot get past an earlier step is wrong in two ways and a fail-closed implementation correctly rejects it at the earlier one — such a vector fails *conforming* implementations. Step 7 is delegation verification and [P-014](P-014-identity-pairing.md) has defined no fixture format for a profile or its evidence, so nothing at or after 7 is authorable: not step 8, whose own defect is expressible, and not steps 10 to 13, whose registry is in hand. Every vector uses `process_query` — ordering is a property of the pipeline, and a `verify_query` vector cannot show the signature was checked *before* the registry was consulted — and each supplies the responder's clock as `environment.now`, since §4 step 6 needs a time and §4.3 forbids a runner from reading one. **Step 2 gets none by design**: §4 makes it optional and never a security decision. [P-010](P-010-responder-pipeline.md) §6 owns the section and its issue 11 completes it once the fixtures exist |
| 15 | Dependency assertion: harness imports no implementation | CI check fails if either is importable from the harness |
| 16 | `semantic` comparison implemented per §4.4 | Array order significant; absent ≠ null; no coercion; both runners agree on a differing-tree report |
| 17 | **Settle the §4.5 operation vocabulary for Stages 5–8, as one change** | **Done.** §4.5 is one table of decided names, and [`vector.schema.json`](../../conformance/vector.schema.json)'s enum carries all of them — the split between a decided list and an anticipated one was itself the divergence hazard, since a PRD reaching Stage 5 would have had to name its operation to author a section and the enum would have refused it. Three things moved in the settling. `http_exchange` lost its registry-entry path ([P-013](P-013-https-binding.md) §4.3). The requester-side ordering need is **`process_response`**, not the "sequence-asserting operation" this section called it — that is a sequence of *steps* over one response, and [E-51](../open-escalations.md) has since taken the word for a sequence of *requests*, so each has its own name and the word names neither. And **`process_sequence`** is new, from E-51, the one entry no PRD proposed because the need arrived as an escalation. **The timing capability is deliberately not named**: issue 18 is undecided, so it is absent from the table and the enum, and a test holds that absence. **Not a blocker for [P-002](P-002-message-envelope.md) issue 10**, which was briefly recorded as one and is not: this issue's remit was the Stage 5–8 extension, and P-002 is Stage 1. Its `message/` groups are authored through `sign_query`, `verify_query`, `process_query` and `digest`, all of which were in the enum already — a serializer is exercised by a vector asserting the bytes it produced, not by an operation named after the function |
| 18 | Minimal timing capability, available at Stage 7 | A vector can assert two response paths fall within a band; [P-015](P-015-escalation-lifecycle.md) issue 4 can be written against it |
| 19 | **Cross-verification: put A's output to B** | §4.8's second cross-implementation clause, split out of issue 9 by §10's resolution. Two PRDs have an acceptance criterion that needs it: [P-003](P-003-crypto-suites.md) §7 and [P-012](P-012-requester-runtime.md) §7. [P-002](P-002-message-envelope.md) §7 does **not** — it asks for byte agreement over `message/`, which issue 9 delivers. **The two runners now exist** — [`src/bin/q2d-conform.rs`](../../src/bin/q2d-conform.rs) and [`cmd/q2d-conform/main.go`](../../cmd/q2d-conform/main.go), contract-only and held to identical behaviour by [`test_runner_parity.py`](../../conformance/tests/test_runner_parity.py) — so what remains is the format: a vector naming its companion artefact and the field that consumes it, which is a format change and protocol knowledge §3 places outside the harness. Still blocked on [P-002](P-002-message-envelope.md) and [P-003](P-003-crypto-suites.md) settling which operation consumes a signed envelope, and on either runner answering anything — cross-verification between two runners that both report `error` shows nothing. **Not optional:** [`mvp-scope.md`](../mvp-scope.md) Stage 1's gate is cross-verification, so this is what makes that gate real. `cross` exits 3 on agreement until it lands |

Issue 16 gated 12 and no longer does. `semantic` is implemented in the harness
([`compare.py`](../../conformance/harness/compare.py)), which is what a vector
author needs; the *"both runners agree"* half of its acceptance is the Stage 1
cross-implementation gate, which no vector in this corpus can satisfy until an
implementation exists — the same position issue 11's registry vectors are in.
Waiting for it would mean authoring nothing until Stage 1, which is the opposite
of what the corpus is for. Issue 17 blocks the corpus sections of
[P-012](P-012-requester-runtime.md) … [P-015](P-015-escalation-lifecycle.md) —
four PRDs naming their own operations would diverge at the *runner* level, which
surfaces as an unknown-operation error rather than a failing vector: the one
failure the corpus cannot catch, because the corpus is what is broken. Issue 1
blocks everything else.
