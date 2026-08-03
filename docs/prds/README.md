# PRD registry

Parent: [`../mvp-scope.md`](../mvp-scope.md). Numbers are permanent once
assigned; an abandoned PRD keeps its number and is marked withdrawn.

| # | Title | Stage | Status |
|---|---|---|---|
| [P-001](P-001-conformance-corpus.md) | Conformance corpus format and harness contract | 0 | **Ready for decomposition** |
| [P-002](P-002-message-envelope.md) | Message envelope and canonical structures | 1 | **Ready for decomposition** |
| [P-003](P-003-crypto-suites.md) | Cryptographic suites, key handling, downgrade policy | 1 | **Ready for decomposition** |
| [P-004](P-004-replay-idempotency.md) | Replay, expiry, idempotency | 1 | **Ready for decomposition** |
| [P-005](P-005-registry-client.md) | Registry client: pinning, resolution, fail-closed | 2 | **Ready for decomposition** |
| [P-006](P-006-request-validation.md) | Request validation and effective answer domain | 2 | **Ready for decomposition** |
| [P-007](P-007-policy-engine.md) | Policy engine contract and fail-closed invariants | 3 | **Ready for decomposition** |
| [P-008](P-008-capacity-accounting.md) | Disclosure-capacity accounting | 3 | **Ready for decomposition** |
| [P-009](P-009-denial-normalization.md) | Denial normalization | 3 | **Ready for decomposition** |
| [P-010](P-010-responder-pipeline.md) | Responder pipeline, predicate execution, output validation | 4 | **Ready for decomposition** |
| [P-011](P-011-receipts-audit.md) | Receipts and local audit | 4 | **Ready for decomposition** |
| P-012 | Requester runtime | 5 | Not authored |
| P-013 | Direct HTTPS binding and custodian daemon | 6 | Not authored |
| P-014 | Identity and the local pairing profile | 6 | Not authored |
| P-015 | Escalation lifecycle | 7 | Not authored |
| P-016 | Reference demonstration and adversarial suite | 8 | Not authored |

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
| **Blocked on escalation** | Complete, but an open question must be decided before implementation begins |
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
