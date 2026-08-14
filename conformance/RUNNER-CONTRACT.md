# The runner contract

What an implementation must ship for the conformance harness to judge it, and
what the harness promises in return.
[`docs/prds/P-001-conformance-corpus.md`](../docs/prds/P-001-conformance-corpus.md)
§4.1, §4.3, §4.6 and §6 are the source; this document is the operational form of
them, and cites rather than restates.

Both implementations must honour it. It is deliberately small: the harness invokes
a subprocess, reads JSON, and compares.

## Invocation

```
q2d-conform <vector-file.json>        →  result JSON on stdout
```

One vector per invocation. The harness supplies the path; the runner reads
nothing else. In particular it is **never given a path to the authored corpus**
(P-001 §4.2), and the file it receives is the projection — `id`, `operation`,
`input`, and nothing more.

## Exit status reports whether the runner functioned

Never whether the vector passed (P-001 §4.1).

| Exit | Meaning |
|---|---|
| 0 | A result was written to stdout. The vector may still fail; the harness decides. This includes a result whose `outcome` is `error`. |
| 1 | The runner could not process the vector — unknown operation, malformed file. No result is written. |
| 2 | A fault so early that no result could be written at all. |

**A vector expecting a rejection is a successful run that reports a rejection**
— exit 0, `outcome: "rejected"`. Conflating "the implementation rejected the
input" with "the runner failed" makes negative acceptance untestable, and
negative acceptance is where this protocol lives.

**The dividing line is whether a result was written, not whether anything went
wrong** (P-001 §4.1). A result whose outcome is `error` is still a result: the
implementation faulted on a vector it understood, said so, and exits 0. Exit 2
is the case where nothing could be written at all. Both fail the vector; the
difference is whether the harness has anything to report about *why*.

## Result format

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
  },
  "implementation": { "name": "q2d-rs", "version": "0.1.0" }
}
```

[`result.schema.json`](result.schema.json) is the machine-checkable form, and
`harness run` validates every result against it before judging anything. A
runner whose output does not conform has not produced a result the harness can
judge, and that is reported as a **runner** failure rather than a vector
failure — one means the implementation is wrong about Q2D, the other means it
is wrong about this contract, and conflating them sends whoever is debugging to
the wrong file.

Three things about that shape:

- **`implementation` is required on every result**, including rejections and
  errors. P-001 §4.6's rejection example omits it for brevity; requiring it is a
  harness decision, because `harness cross` compares two runners' output and a
  result that does not say who produced it is unattributable in the report that
  matters most.
- **`step`** is the [`core-model.md`](../spec/core-model.md) §4 step at which
  rejection occurred, and is how ordering is asserted without instrumenting the
  implementation. Optional in general; the `ordering/` section is where it is
  the point.
- **The internal reason and the wire response are separate fields**, because
  they are separate values in a conforming implementation
  ([`core-model.md`](../spec/core-model.md) §5.2). A runner that derives one
  from the other has already lost the property the corpus is checking.

## What a runner must not do

- **Read a clock, or generate a nonce, key, or identifier.** Every value that
  would otherwise vary is supplied by the vector (P-001 §4.3). A runner that
  reads ambient state produces an unreproducible result and is non-conforming —
  and the cross-implementation comparison stops being a byte comparison, which
  is the property the Stage 1 gate rests on.
- **Read anything but the vector file it was given** — including this
  repository. A runner that consulted `vector.schema.json` for the operation
  vocabulary would answer differently depending on the checkout it ran in, and
  the shipped Rust and Go runners will not have the corpus to consult anyway.
  Embed what you need; a vocabulary that has drifted shows up as exit 1 on a
  vector the corpus expects you to answer, which is the loud failure.
- **Answer a file carrying anything but `id`, `operation`, and `input`.** P-001
  §6 fixes that shape. An extra field means the file is not a projection, and
  the extra field that matters is `expect`: a runner holding an expectation was
  handed the authored vector, so the harness failed to project it and the
  corpus has stopped being evidence. Exit 1 rather than answer. The harness
  holds the first key to that door; this is the second lock, and it costs one
  comparison.
- **Parse permissively.** `NaN`, `Infinity`, and duplicate object keys are not
  JSON (RFC 8259), and a runner that accepts them accepts a file another runner
  rejects — the divergence the shared corpus exists to surface, arriving inside
  the thing meant to surface it. A vector file that is not JSON is exit 1.
- **Decide its own pass or fail.** The implementation reports; the harness
  judges (P-001 §9.4). A runner that reads an expectation could not have got one
  from the harness, so a runner that has one has found the authored corpus.
- **Print anything else on stdout.** Diagnostics go to stderr. The harness
  parses stdout as one JSON document.

## Operations

The closed vocabulary is P-001 §4.5, and
[`vector.schema.json`](vector.schema.json)'s `operation` enum is its
machine-checkable form. **An operation a runner does not recognise is exit 1,
never a skip** — fail-closed applies to runners too, and a skipped vector is a
vector nobody notices is unimplemented.

## The reference stub

[`runners/stub/q2d-conform`](runners/stub/q2d-conform) implements this contract
and nothing else: it reports `error` for every operation. It exists so the
harness can be developed and tested against a runner before either
implementation exists, and so that P-001 §7's gate — *the harness runs and
reports fail for every vector* — is demonstrable rather than asserted.

It is not a partial implementation and must never become one. The moment the
stub answers a vector correctly, the harness is being tested against something
that shares an author with the corpus.

## The two implementation runners

[`src/bin/q2d-conform.rs`](../src/bin/q2d-conform.rs) and
[`cmd/q2d-conform/main.go`](../cmd/q2d-conform/main.go) are the Rust and Go
runners. They implement this contract and, today, no Q2D behaviour: every
operation reports `error`, exactly as the stub does.

**Unlike the stub, they may learn to answer.** They are the reference
implementations' runners and the corpus exists to be run against them; the stub
may not, because it shares an author with the harness.

They exist now, before either implementation does, for two reasons. The contract
is demonstrably implementable in both languages rather than assumed to be — and
`harness cross` reports a disagreement as *two implementations reading the
specification differently*, an inference that only holds if everything around
the protocol already matches. A runner that accepted a duplicate object key
while the other refused it would make `cross` report a divergence about JSON.

[`tests/test_runner_parity.py`](tests/test_runner_parity.py) holds them to that:
twenty-six documents, twenty-two of which must be **refused** and four
**accepted**, with the same exit code from both for each.

Most are chosen because a permissive parser would differ on them: duplicate keys
at two depths, `NaN`, `Infinity`, a trailing document, an unescaped control
character, a file that is not valid UTF-8, a lone surrogate of each half, and
eight numeric forms RFC 8259 §6 forbids. **Three** of the accepted ones are the
other half of that — a valid surrogate pair and two numbers outside `float64`'s
range, which a runner must not refuse. The fourth is an ordinary projection,
which is there so the suite is not satisfied by a runner that refuses
everything.

The rest are **contract** cases rather than parser ones — an unprojected vector
carrying `expect`, an unknown operation, a missing `input`, a non-string `id`, a
top-level array. They belong here for the same reason: two runners that disagreed
about any of them would disagree about a vector without disagreeing about Q2D. A list of refusals alone is satisfied by a
runner that refuses everything, and one that rejects valid vectors is worse than
a permissive one — it fails a conforming producer.

Five of those cases were divergences when first written, all about encoding
rather than about Q2D: Go substituted U+FFFD for malformed UTF-8 and for an
unpaired surrogate where Rust refused both, and Rust refused the first half of a
valid pair where Go decoded it, and Rust validated numbers with `f64::from_str`,
which accepts `01` and `1.` where `encoding/json` refuses them. Go, in turn,
converted every number to `float64` and so refused `1e400`, a valid RFC 8259
number the Rust scanner accepts — fixed with `UseNumber`, since neither runner
has any use for a numeric value. Each would have surfaced through `cross` as two
implementations disagreeing about the protocol. Establishing the parity now is
cheapest, because with neither answering a vector there is nothing else a
difference could be blamed on.

Neither takes a dependency. `encoding/json` already refuses `NaN`; it keeps the
last of a duplicate key silently, which RFC 8259 calls unpredictable and which
two runners must not resolve differently — so both refuse, and the Rust one
hand-writes a scanner rather than inheriting some crate's defaults for the
behaviour this contract is most specific about.
