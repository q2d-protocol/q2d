# PRD registry

Parent: [`../mvp-scope.md`](../mvp-scope.md). Numbers are permanent once
assigned; an abandoned PRD keeps its number and is marked withdrawn.

**Twelve active, five deferred, one new** — the 2026-08-19 scope reduction.
Deferred is not withdrawn: each deferred PRD keeps its number, its issue list and
its reasoning, with a status header saying why it stopped and what would bring it
back. Reasoning in `private-docs/scope-reduction-proposal.md`.

**What changed.** The project's goal was restated as a *demonstration people can
import and configure* rather than a protocol being hardened for adoption. The
headline claim became **Q2D-C-03** — a bounded answer domain gives an injected
payload no channel to return through — and the binding became **MCP** rather than
a bespoke HTTPS daemon. Five PRDs were deferred: the disclosure-capacity budget,
the contained requester runtime, the HTTPS binding, the pairing profile, and the
escalation lifecycle.

**Escalations.** **[E-52](../open-escalations.md) is open and parked with
[P-015](P-015-escalation-lifecycle.md)** — a sequence cannot carry an event
between its requests, and an approval is one. It blocks four of P-015's eight
`escalation/` groups, which are themselves deferred, so it blocks nothing
startable. **[E-01](../open-escalations.md) and E-25 … E-30** park with
[P-008](P-008-capacity-accounting.md): the enum-coarsening and capacity chain has
no consumer while the budget is deferred. Parked means *undecided with no
consumer*, not *closed*.

**This paragraph used to say "No escalation is open" while E-51 had been open for
four PRDs' worth of work**, and it had accreted two different escalations each
described as "the last". That is the failure the escalation register exists to
prevent, occurring in the file most likely to be read as a status summary. The
register — [`../open-escalations.md`](../open-escalations.md) — is authoritative
for what is open; this file states the shape and links.

| # | Title | Stage | Status |
|---|---|---|---|
| [P-001](P-001-conformance-corpus.md) | Conformance corpus format and harness contract | 0 | **Ready for decomposition** |
| [P-002](P-002-message-envelope.md) | Message envelope and canonical structures | 1 | **Ready for decomposition** |
| [P-003](P-003-crypto-suites.md) | Cryptographic suites, key handling, downgrade policy | 1 | **Ready for decomposition** |
| [P-004](P-004-replay-idempotency.md) | Replay, expiry, idempotency | 1 | **Ready for decomposition** |
| [P-005](P-005-registry-client.md) | Registry client: pinning, resolution, fail-closed | 2 | **Ready for decomposition** |
| [P-006](P-006-request-validation.md) | Request validation and effective answer domain | 2 | **Ready for decomposition** |
| [P-007](P-007-policy-engine.md) | Policy engine contract and fail-closed invariants | 3 | **Ready for decomposition** — shrunk |
| [P-008](P-008-capacity-accounting.md) | Disclosure-capacity accounting | — | **Deferred** — a request quota replaces it |
| [P-009](P-009-denial-normalization.md) | Denial normalization | 3 | **Ready for decomposition** — shrunk to one refusal shape |
| [P-010](P-010-responder-pipeline.md) | Responder pipeline, predicate execution, output validation | 4 | **Ready for decomposition** |
| [P-011](P-011-receipts-audit.md) | Receipts and local audit | 4 | **Ready for decomposition** |
| [P-012](P-012-requester-runtime.md) | Requester runtime | 5 | **Deferred** — four issues survive as a test client |
| [P-013](P-013-https-binding.md) | Direct HTTPS binding and custodian daemon | — | **Deferred** — superseded by P-017 |
| [P-014](P-014-identity-pairing.md) | Identity and the local pairing profile | — | **Deferred** — configured key list instead |
| [P-015](P-015-escalation-lifecycle.md) | Escalation lifecycle | — | **Deferred** — carries E-52 |
| [P-016](P-016-demonstration-adversarial.md) | Reference demonstration and adversarial suite | 5 | **Ready for decomposition** — shrunk; gains the injection demo |
| [P-017](P-017-mcp-binding.md) | MCP binding | 5 | **Ready for decomposition** — new |

## Authoring order

**The full set is authored before any implementation code is written**, then kept
in lockstep with the code as development proceeds.

Authoring all sixteen first surfaces interface mismatches between modules while
they are still paragraphs. It also front-loads the cheapest review of the
specification available: a PRD that cannot state its acceptance without inventing
a requirement has found a spec gap, and finding sixteen of those before Stage 1
is worth more than finding them one stage at a time.

Lockstep afterwards means a PRD is amended in the same change as the code that
diverges from it. A PRD that describes what the code used to do is worse than no
PRD, because it is trusted.

## Status vocabulary

| Status | Means |
|---|---|
| Not authored | Placeholder; the row reserves the number |
| Draft | Being written; sections incomplete |
| **Ready for decomposition** | Every section in [`../mvp-scope.md`](../mvp-scope.md) §5 is complete and the issue list is enumerated |
| **Blocked on escalation** | Complete, but an open question must be decided before implementation begins. Record it in [`../open-escalations.md`](../open-escalations.md), whose per-entry **Cascade** line is the checklist for closing it |
| In progress | Issues are being executed |
| Done | Acceptance and negative acceptance pass in both implementations |

A PRD is not ready without **negative acceptance**. For a protocol whose value is
what it refuses, a PRD listing only what must succeed is untestable.

## What every PRD contains

Purpose and the claims it serves · spec citations by identifier · module boundary
· language-neutral interfaces · corpus sections · acceptance stated as *"both
implementations pass X"* · negative acceptance · escalate-if-changed decisions ·
open questions · issue list.

**PRDs cite the specification; they never paraphrase it.** A paraphrase is a
second source of truth and it drifts. Where a PRD author finds the spec
ambiguous, that is a spec bug — fix [`../../spec/`](../../spec/), then cite the
fix. Resolving it inside a PRD is how two implementations diverge while both pass
their own documents.
