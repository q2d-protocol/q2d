# PRD registry

Parent: [`../mvp-scope.md`](../mvp-scope.md). Numbers are permanent once
assigned; an abandoned PRD keeps its number and is marked withdrawn.

| # | Title | Stage | Status |
|---|---|---|---|
| [P-001](P-001-conformance-corpus.md) | Conformance corpus format and harness contract | 0 | **Ready for decomposition** |
| P-002 | Message envelope and canonical structures | 1 | Not authored |
| P-003 | Cryptographic suites, key handling, downgrade policy | 1 | Not authored |
| P-004 | Replay, expiry, idempotency | 1 | Not authored |
| P-005 | Registry client: pinning, resolution, fail-closed | 2 | Not authored |
| P-006 | Request validation and effective answer domain | 2 | Not authored |
| P-007 | Policy engine contract and fail-closed invariants | 3 | Not authored |
| P-008 | Disclosure-capacity accounting | 3 | Not authored |
| P-009 | Denial normalization | 3 | Not authored |
| P-010 | Responder pipeline, predicate execution, output validation | 4 | Not authored |
| P-011 | Receipts and local audit | 4 | Not authored |
| P-012 | Requester runtime | 5 | Not authored |
| P-013 | Direct HTTPS binding and custodian daemon | 6 | Not authored |
| P-014 | Identity and the local pairing profile | 6 | Not authored |
| P-015 | Escalation lifecycle | 7 | Not authored |
| P-016 | Reference demonstration and adversarial suite | 8 | Not authored |

## Status vocabulary

| Status | Means |
|---|---|
| Not authored | Placeholder; the row reserves the number |
| Draft | Being written; sections incomplete |
| **Ready for decomposition** | Every section in [`../mvp-scope.md`](../mvp-scope.md) §5 is complete and the issue list is enumerated |
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
