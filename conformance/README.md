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
python3 conformance/harness lint --corpus DIR       # any directory of vectors
python3 -m unittest discover -s conformance/tests   # the harness's own tests
```

Standard library only, like [`registry/validate.py`](../registry/validate.py).

## State

**The corpus is empty and most of the harness does not exist yet.** Built so far:
the vector schema and `lint` (P-001 issue 1). `run`, `cross`, and `coverage`
exit non-zero saying which issue owns them — P-001 §7 asks for a harness that
reports fail because no implementation exists, and a mode that silently
succeeded would be worse than one that is missing.

That has a consequence for CI worth stating before someone hits it. When `run`
lands it is red by design until Stage 1 does, and a permanently red check trains
people to ignore red. The rule, which
[`.github/workflows/checks.yml`](../.github/workflows/checks.yml) carries: when
those modes exist, assert the expected state — *the harness reports fail-all*,
*coverage reports thirteen uncovered claims* — rather than running a check that
fails.

**Neither assertion is in CI today, because neither mode exists.** What is:
[`tests/test_harness_cli.py`](tests/test_harness_cli.py) holds the unbuilt modes
to exiting non-zero, and turns red the day one is built — which is the moment to
add its assertion.

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

**It imports neither implementation** (P-001 §9.2). Sharing code with one would
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
