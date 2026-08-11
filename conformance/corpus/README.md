# Corpus

Vectors live here, one directory per section. A vector's `section` field, the
first segment of its `id`, and the directory it sits in must all agree;
`harness lint` checks that they do.

**The corpus is empty.** Sections are authored by the PRD that owns the
behaviour they exercise, against the format in
[`../vector.schema.json`](../vector.schema.json):

| Section | Authored by |
|---|---|
| `message/` | [P-002](../../docs/prds/P-002-message-envelope.md) |
| `suite/` | [P-003](../../docs/prds/P-003-crypto-suites.md) |
| `replay/` | [P-004](../../docs/prds/P-004-replay-idempotency.md) |
| `registry/` | [P-005](../../docs/prds/P-005-registry-client.md), folding in [`registry/manifest.json`](../../registry/manifest.json)'s vectors |
| `domain/` | [P-006](../../docs/prds/P-006-request-validation.md) |
| `policy/` | [P-007](../../docs/prds/P-007-policy-engine.md) |
| `budget/` | [P-008](../../docs/prds/P-008-capacity-accounting.md) |
| `denial/` | [P-009](../../docs/prds/P-009-denial-normalization.md) |
| `ordering/`, `evaluate/`, `validate/`, `pipeline/` | [P-010](../../docs/prds/P-010-responder-pipeline.md) |
| `receipt/` | [P-011](../../docs/prds/P-011-receipts-audit.md) |
| `requester/` | [P-012](../../docs/prds/P-012-requester-runtime.md) |
| `binding/` | [P-013](../../docs/prds/P-013-https-binding.md) |
| `identity/` | [P-014](../../docs/prds/P-014-identity-pairing.md) |
| `escalation/` | [P-015](../../docs/prds/P-015-escalation-lifecycle.md) |
| `demo/`, `adversarial/` | [P-016](../../docs/prds/P-016-demonstration-adversarial.md) |

Stage 0 authors `message/`, `suite/`, and `ordering/` itself
([P-001](../../docs/prds/P-001-conformance-corpus.md) §5, issues 12–14).

An empty corpus lints green, and that means nothing: `harness lint` says the
corpus is empty rather than reporting a clean run over no evidence. What an
empty corpus should report is thirteen uncovered claims, which is
[P-001](../../docs/prds/P-001-conformance-corpus.md) issue 6's `harness coverage`.
