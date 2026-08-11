# Claude Code Context — Q2D

You are the implementing agent on Q2D. This file is your standing brief. Read it
before touching anything.

## What Q2D is

A transport-neutral protocol for policy-bound, least-disclosure answers over data
held by a participating custodian. A requester signs an **answer contract** — the
predicate, purpose, recipient, permitted sinks, maximum response domain — before
any evaluation happens. The custodian verifies it against a pinned predicate
registry, applies policy locally, evaluates over data that never crosses the
interface, and returns a bounded authenticated answer with a disclosure receipt.

Pre-release. The technical report is published
([10.5281/zenodo.21777306](https://doi.org/10.5281/zenodo.21777306)); the
specification spine exists; the reference implementations do not yet.

**This is a protocol project, not a product.** Nobody is shipping a feature.
Everything here exists to make a specification true, checkable, and honest.

## Priorities, in order

When two of these conflict, the earlier one wins.

1. **Claim honesty.** The project's entire credibility rests on
   [`spec/claims.md`](spec/claims.md) being exactly true. Code that quietly
   delivers less than a claim states is worse than code that doesn't exist —
   an implementer would rely on it.
2. **Spec fidelity.** The code implements the specification. Where they disagree,
   one of them is a bug and you must say which.
3. **Cross-implementation agreement.** Rust and Go must behave identically. A
   divergence is a finding, not a variation.
4. **Security.** Ordering, fail-closed behaviour, absence of oracles.
5. **Clarity.** This code is read by reviewers deciding whether to trust the
   protocol. Legibility outranks cleverness everywhere.

Performance is not on this list. It becomes relevant at Stage 8's measurements
and not before.

## Authoritative context hierarchy

Higher wins. This is the single most important rule in the repository.

```
1. spec/ and threat-model/     what must be true
2. registry/manifest.json      predicate definitions, domains, capacities
3. docs/mvp-scope.md           stage order, gates, decomposition
4. PRDs                        how a module is built and verified
5. code                        the implementation
```

**A PRD cites the spec; it never paraphrases it.** A paraphrase is a second
source of truth, and two sources of truth drift. If a PRD needs to explain a
requirement, it quotes the identifier — `Q2D-C-03`, `core-model.md` §4 step 12 —
and links.

**If the spec is ambiguous, that is a spec bug.** Fix `spec/`, then cite the fix.
Never resolve an ambiguity inside a PRD or in code. That is precisely how two
implementations diverge while both pass their own documents.

## Repo topology

```
spec/                normative definitions      — governs everything below
threat-model/        trusted computing base per claim
registry/            reference predicate manifest + validator
conformance/         shared vector corpus + harness (imports neither implementation)
docs/                mvp-scope.md, versioning.md, operator docs
paper/               technical report + reproducible build pipeline
website/             q2d.dev  (serves the go-import tag — load-bearing)
tools/               repo-wide hygiene checks CI runs
.github/workflows/   CI — everything in it must be green; see below
private-docs/        gitignored: strategy, external review, decision record
```

`src/` and `go.mod` are placeholders holding the crate and module names. Real
implementations land under the plan in `docs/mvp-scope.md`.

## The workflow

```
plan → implement → self-review → commit locally → CODEX REVIEW → address → repeat until clean → push → PR → merge
```

**Codex reviews the local commit before it is pushed.** Never push, and never
open a PR, until Codex returns clean. Its brief is [`AGENTS.md`](AGENTS.md) —
read it so you know what it will catch, and pre-empt those findings in your own
self-review rather than spending rounds on them.

Merge with a merge commit, never squash. Individual commits carry the reasoning.

### CI is green or it is broken

[`.github/workflows/checks.yml`](.github/workflows/checks.yml) contains nothing
that is expected to fail. That is a rule, not a description of today.

It matters here because this project has a gate that is deliberately red:
[`P-001`](docs/prds/P-001-conformance-corpus.md) §7 wants the harness to report
fail for every vector until an implementation exists. **When you build
`harness run` or `harness coverage`, do not add it to CI as a failing job.** A
permanently red check trains everyone to ignore red, and the cost lands on the
day it starts meaning something.

Assert the expected state instead — "the harness reports fail-all", "coverage
reports thirteen uncovered claims". Each is green while true and turns red when
someone changes the thing without changing the expectation, which is the signal
you wanted.

Neither mode exists yet, so neither assertion is in CI. The one that is:
`conformance/tests/test_harness_cli.py` holds the unbuilt modes to exiting
non-zero, and turns red the day one of them is built — which is when to add its
assertion.

## Self-review before Codex handoff

Work through this list. Most of it exists because the failure already happened
in this repository.

### Spec fidelity

- [ ] Every non-obvious behaviour cites the requirement it implements, by identifier.
- [ ] Nothing paraphrases a spec requirement in a comment or doc where a citation would do.
- [ ] If you found the spec ambiguous, you changed `spec/` — you did not decide locally.
- [ ] If you changed `spec/`, you checked whether `claims.md`,
      `conformance-classes.md`, and `trust-matrix.md` still agree with it.
- [ ] If the change closes an escalation, you worked
      [Closing an escalation](#closing-an-escalation) — the decision is the easy
      half.

### Claim honesty

- [ ] No code, comment, README, or commit message asserts something not in
      [`spec/claims.md`](spec/claims.md).
- [ ] Nothing uses a prohibited term from
      [`spec/terminology.md`](spec/terminology.md) §9. "Cryptographically proven",
      "wire-level indistinguishability", "post-quantum ready", "leakage budget",
      and "compliance-by-construction" are the recurring ones.
- [ ] A claim you cannot test is described as a design intention, not a property.

### Cross-implementation agreement

- [ ] The change is language-neutral in design. Anything language-specific is
      idiom, and belongs in `CONVENTIONS-{rust,go}.md`, not in a PRD.
- [ ] New behaviour has a shared corpus vector, and both implementations are
      expected to produce identical output for it.
- [ ] **No floating-point arithmetic in budget accounting.** Capacity is integer
      millibits, read from the registry.
- [ ] **No `log2` call at runtime.** IEEE-754 does not guarantee a correctly-rounded
      `log2`; the registry carries the value precisely so implementations cannot
      disagree. See [`core-model.md`](spec/core-model.md) §3.1.
- [ ] No iteration order, map ordering, or hash seed can affect an output.

### Protocol correctness

- [ ] Signature verification precedes parsing of the object it covers.
- [ ] Nothing reads private input before [`core-model.md`](spec/core-model.md) §4
      step 16.
- [ ] `routing` is never used for a decision the signature covers.
- [ ] Effective answer domain is computed by the responder; no requester-asserted
      domain or debit is trusted anywhere.
- [ ] Every failure path is fail-closed. Unknown, missing, and indeterminate all
      deny.
- [ ] No private value can reach an error message, log line, or serialized
      exception.

### Denial normalization

- [ ] The **internal reason** and the **external response** are separate values
      and never the same variable.
- [ ] Every rejection in a normalized class returns a byte-identical wire
      response. Test this across causes, not per-cause — a per-case test cannot
      catch the divergence.
- [ ] Response size does not vary with cause.
- [ ] No cause-specific retry guidance.

### Version and metadata hygiene

- [ ] Version numbers agree everywhere they appear. **This has failed three times
      in this repository** — packaging metadata naming "Draft 0.2", release notes
      naming the prior draft, and the manuscript's versioning note and
      public-release sequence both naming 0.2.1 while everything else said 0.2.2.
      Each read as correct prose. Each was wrong. Grep for the old number before
      claiming a version bump is done.
- [ ] `website/index.html` still carries the `go-import` and `go-source` meta
      tags if you touched it. They are load-bearing for the Go module path.
- [ ] If you changed `conformance/vector.schema.json`, the served copy at
      `website/conformance/vector.schema.json` matches it byte for byte. The
      schema's `$id` points at that URL, so a stale copy publishes a format
      nothing in the repository agrees with. A test asserts it.

### Hygiene

- [ ] Tests exist for the negative cases, not just the positive ones. For this
      protocol the interesting behaviour is what it refuses.
- [ ] Cross-document links resolve.
- [ ] No secrets, no real personal data. Test fixtures are synthetic.

## PRD scoping check

Before implementing against a PRD, confirm it has all of: purpose and the claims
it serves, spec citations by identifier, module boundary, language-neutral
interfaces, corpus sections, acceptance stated as "both implementations pass X",
**negative acceptance**, escalate-if-changed decisions, open questions, and an
issue list.

A PRD missing negative acceptance is not ready. Say so rather than filling the
gap yourself.

## When to escalate vs. decide

**Decide yourself:** naming, file layout, test structure, error-message wording
that carries no private data, refactors inside one module, anything the spec
already determines.

**Escalate to Peter:**

- Any change to `spec/`, `threat-model/`, or `registry/manifest.json` semantics.
  Editorial fixes are yours; meaning is not.
- Anything that would alter, weaken, or add a claim in `claims.md`.
- A discovered spec ambiguity where more than one resolution is defensible.
- A change to the processing order in `core-model.md` §4.
- Adding a cryptographic suite, or changing the capacity unit.
- Anything that would make the two implementations diverge deliberately.
- A predicate's answer domain, capacity, or sensitivity classification.
- Anything touching the deposited report. It has a DOI and is immutable;
  corrections take a new draft number.

When escalating, state the options and your recommendation. Do not present a
menu without a view.

## Closing an escalation

An escalation is not closed when the decision is made. It is closed when every
document that carried the old rule carries the new one.

**This has already failed.** The subsetting resolution — P-006 escalated it, it
was decided as coarsening-only — amended `core-model.md` §2.5,
`terminology.md` §6, and `claims.md` Q2D-C-09, and missed `scope.md` §4 and
`mvp-scope.md` §4. Both still told a requester it *"may request a subset"* for
four PRDs afterwards. `scope.md` is in `spec/` and therefore governs, so an
implementer working from it would have built the zero-debit oracle the
escalation existed to close, while passing every other document.

The failure was propagating file by file. Two of the four documents carrying the
rule were amended by hand, and nothing checked the other two.

**Then it failed a second time, in the fix.** Grepping the exact phrase
`"subset or a coarser"` found those two and missed a third — P-006's own citation
table, which had paraphrased the rule as `subset-or-coarser`. The PRD that raised
the escalation was still describing the superseded rule four PRDs later. A phrase
search finds the documents that copied the old wording verbatim and misses every
one that put it in its own words, which is most of them.

Work this list when a decision comes back:

- [ ] **Grep for the concept, not the phrase, and read every hit.** One
      distinctive *word* — `subset`, `log2`, `millibit` — across `spec/`,
      `threat-model/`, `registry/`, `docs/`, and `docs/prds/`. It will return
      correct uses too; that is the cost, and it is much lower than the cost of
      missing one. Do not grep the identifier: `§2.5` appears wherever the rule is
      cited correctly as well as wherever it is stated wrongly, so it buries the
      dangerous hits among the safe ones.
- [ ] **Include the PRD that raised the escalation.** It is the document most
      likely to be assumed clean and, having argued the case at length, the one
      most likely to state the old rule somewhere other than where it recorded the
      resolution.
- [ ] Where a PRD narrates the discovery, put the superseded text in the **past
      tense** and mark it as historical. A live-sounding sentence describing what
      the spec used to say reads as what it says now.
- [ ] Amend every hit, or say in the commit why one is deliberately unchanged.
- [ ] Re-check the three documents that describe the spec to itself:
      `claims.md`, `conformance-classes.md`, `trust-matrix.md`. A resolution that
      changes a mechanism usually changes what a claim rests on.
- [ ] Mark the open question resolved **in the PRD that raised it**, naming the
      section that now carries the answer — not only in the commit message. A
      commit is not where the next reader looks.
- [ ] Update every PRD that delegated a question to it, and every PRD that
      recorded the same escalation from its own side.
- [ ] If the resolution changes what gets built, change the PRD's status and its
      affected issues. A PRD that leaves **Blocked on escalation** with its issue
      list unchanged has recorded the decision without absorbing it.
- [ ] Re-run the mechanical checks: cross-document links resolve, and the PRD
      dependency graph is still symmetric.

This is the same failure class as the version-number drift above. Both are a rule
living in more places than the person changing it remembered.

## What NOT to do

- **Do not add a claim.** Claims are decided in `spec/claims.md`, deliberately,
  with assumptions and failure modes. Code does not get to introduce one.
- **Do not compute capacity.** Read it from the registry.
- **Do not let an internal reason reach the wire.**
- **Do not resolve a spec ambiguity in code or in a PRD.**
- **Do not write a second PRD set for the second language.**
- **Do not describe the two implementations as "independent".** Both are by the
  same author. They demonstrate the spec is *implementable*; that is the real and
  sufficient claim.
- **Do not edit the published report package.** `paper/Q2D_..._v0.2.2_Source_Package/`
  is deposited. Corrections go into a new draft.
- **Do not commit `private-docs/`.** It is gitignored for cause — strategy,
  external review, commercial material.
- **Do not push before Codex is clean.**

## Running locally

```sh
# Registry manifest: internal consistency + every test vector
python3 registry/validate.py

# Conformance corpus: schema self-checks over the vector set
python3 conformance/harness lint
python3 -m unittest discover -s conformance/tests

# Cross-document links — the same check CI runs
python3 tools/check_links.py

# Technical report: build and run the deposit checks
cd paper && make DRAFT=0.2.2 PAGES=43 verify
cd paper && make repro          # rebuild 0.2.1 and diff against the published DOCX

# Once implementations exist
cargo test                      # Rust
go test ./...                   # Go
# conformance harness across both — Stage 0 deliverable, not yet built
```

## Commit and PR conventions

Commits explain **why**, not what — the diff shows what. Where a decision had a
defensible alternative, say which and why it lost. Where a change fixes a class
of bug rather than an instance, say so.

PR bodies lead with the substance, not a file list. If the work surfaced a
problem that is *not* fixed by the PR, the body says so plainly rather than
leaving it for a reader to notice.

Both end with:

```
Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: <session url>
```

## A note on tone in artifacts

Everything in this repository is read by people deciding whether to trust a
protocol. Overstatement is the failure mode that costs most, and it is
frictionless — it happens in a comment, a README line, a commit message. The
non-claims list in `claims.md` is longer than the claims list on purpose. Keep it
that way.
