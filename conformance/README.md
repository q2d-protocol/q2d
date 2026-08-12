# Conformance corpus and harness

The shared test corpus, and the language-agnostic harness that runs it against
any implementation. [`docs/prds/P-001-conformance-corpus.md`](../docs/prds/P-001-conformance-corpus.md)
is the source of truth for everything here; this file says where things are and
how to run them, and cites the PRD rather than restating it.

```
conformance/
  vector.schema.json   the authored vector format, machine-checkable  (P-001 §4.4)
  result.schema.json   what a runner writes back                      (P-001 §4.6)
  RUNNER-CONTRACT.md   what an implementation must ship               (P-001 §4.1)
  harness/             the harness                                    (P-001 §4.7)
  runners/stub/        the reference runner: answers nothing, on purpose
  corpus/              vectors, one directory per section             (P-001 §5)
  tests/               the harness's own tests
```

The schema's `$id` is `https://q2d.dev/conformance/vector.schema.json`, and
[`website/conformance/vector.schema.json`](../website/conformance/vector.schema.json)
is what serves it — a byte-identical copy, because `website/` is the published
site root and nothing builds it. **Change the schema and you change both**; a
test fails naming the stale one if you do not.

## Running it

```sh
python3 conformance/harness lint                    # corpus self-checks
python3 conformance/harness run --impl PATH         # a corpus against one runner
python3 conformance/harness coverage                # claims with no citing vector
python3 conformance/harness cross --a P --b P       # two runners, held to agreeing
                                                   #   0 never, today: see below
                                                   #   1 they diverged, or a vector
                                                   #     could not be compared
                                                   #   2 nothing ran — bad usage,
                                                   #     missing runner, bad corpus
                                                   #   3 they agreed, and §4.8's
                                                   #     second clause is issue 19
python3 -m unittest discover -s conformance/tests   # the harness's own tests
```

Both modes take `--corpus DIR` to point at a directory other than
[`corpus/`](corpus). Running the corpus against the reference stub is what
P-001 §7's gate looks like today:

```
$ python3 conformance/harness run --impl conformance/runners/stub/q2d-conform --corpus conformance/tests/fixtures/valid
  FAIL  denial/uniformity-c/unknown-predicate
          expected outcome 'rejected', got 'error' (the reference stub implements no Q2D behaviour)
  FAIL  message/sign/query-minimal
          expected outcome 'ok', got 'error' (the reference stub implements no Q2D behaviour)

0/2 vectors passed
```

Standard library only, like [`registry/validate.py`](../registry/validate.py).

## State

**Every mode exists; the corpus is empty and there is nothing to run it
against.** Built: the vector schema and `lint` (issue 1), the projection
(issue 2), the runner contract and reference stub (issue 3), `run` (issue 4),
the determinism check (issue 5), `coverage` (issue 6), the two cross-vector
assertions (issues 7 and 8), comparison (issue 16), `cross` (issue 9), and the
dependency assertion (issue 15).

`cross` is **half of what P-001 §4.8 asks**: it compares what two runners each
produced, and does not put A's output to B for verification, which is issue 19.
It says so on every run and exits 3 — not 0 — when the runners agree, so nothing
can read the clause off its status. (3, not 2: 2 is the status for nothing
having run at all.) Whether that split is accepted is an open
question in P-001 §10, awaiting a decision.

That has a consequence for CI worth stating before someone hits it. `run` is red
by design until Stage 1 lands, and a permanently red check trains people to
ignore red. The rule, which
[`.github/workflows/checks.yml`](../.github/workflows/checks.yml) carries: assert
the expected state rather than running a check that fails.

**The harness depends on neither implementation, and that is checked rather
than trusted** — [`tests/test_dependencies.py`](tests/test_dependencies.py)
resolves every import the harness makes and fails on anything that is not
stdlib or a sibling module, and on any implementation path named in source.
P-001 §9 makes the rule escalate-if-changed because shared code means shared
bugs that cancel out; §7 asks for it *"asserted by dependency check, not by
convention"*, and a convention is what a check like this replaces.

**Three expected-state assertions are in CI**, in place of jobs that would be
red by design: no vector in the real corpus passes against the reference stub,
all thirteen claims are uncovered, and the stub against itself compares nothing.
Each is green while true and red the day it stops being — which is the day
someone should be adding a real assertion in its place.

## What a vector looks like

The shape, with [`vector.schema.json`](vector.schema.json) as the authority and
P-001 §4.4 as the reasoning:

```json
{
  "id": "message/sign/query-minimal",
  "section": "message",
  "requirement": ["Q2D-C-05", "core-model.md#2.1"],
  "description": "A minimal signed query envelope with an advisory routing projection.",
  "operation": "sign_query",
  "input": { "key_id": "test-requester-1", "query": {} },
  "expect": { "outcome": "ok", "output": {}, "comparison": "bytes" }
}
```

Four things about that file are load-bearing, and each is a rule the PRD gives a
reason for rather than a preference:

- **`requirement` and `comparison` are mandatory with no default.** A vector
  citing nothing is not traceability, and a defaulted comparison mode is how a
  determinism requirement gets quietly dropped. P-001 §4.4.
- **`expect` never reaches an implementation.** The harness writes an input-only
  projection; implementations are not given a path to the authored corpus. An
  implementation that can read the expected output can pass by reproducing it.
  P-001 §4.2. [`harness/projection.py`](harness/projection.py) builds it from
  the **allowlist** `{id, operation, input}` rather than by deleting `expect` —
  a delete keeps the rule true only for the fields someone thought of, and a
  later `expected` or `notes_for_the_runner` would sail through it.
- **Everything that would otherwise vary comes from `input`** — keys, nonces,
  timestamps, identifiers. A runner that reads a clock or generates a nonce
  produces an unreproducible result and is non-conforming. P-001 §4.3.
- **`operation` is a closed vocabulary.** The Stage 5–8 additions are named in
  P-001 §4.5 as *proposals* and are deliberately absent from the schema until
  P-001 issue 17 settles them as one change; four PRDs choosing separately would
  diverge at the runner level, where it surfaces as an unknown-operation error
  rather than a failing vector.

`expect.outcome` is `ok` or `rejected`. `error` is a third outcome a *runner*
may report (P-001 §6) and means the runner faulted — never something a vector
expects, because an internal error is not a passing result.

## Two properties of the harness worth not losing

**It imports neither implementation** (P-001 §9, decision 2). Sharing code with one would
let the harness inherit a bug from it: a canonicalization or digest error
present in both would cancel out and the suite would pass. A third language
rules out *shared code*, and P-001 issue 15 turns that into a CI check.

It does not rule out shared *mistakes*. The harness can still read the
specification the same wrong way both implementations do, and no arrangement of
our own code detects that — only a third implementation someone else writes
does. What the separation buys is that a defect has to be made twice, not once.

**Its schema validator refuses unknown keywords.** `harness/schema.py` covers
exactly the JSON Schema keywords `vector.schema.json` uses, and raises rather
than skipping anything else — a validator that ignored a keyword would let the
schema state a constraint nothing enforced. Adding a keyword to the schema means
adding it to the validator, and the error says so.
