# PRD registry

Parent: [`../mvp-scope.md`](../mvp-scope.md). Numbers are permanent once
assigned; an abandoned PRD keeps its number and is marked withdrawn.

All sixteen are ready for decomposition, with two issues held by an open escalation — see the status column. **One escalation is open**: **E-28**, a claim-honesty item — `object` is bounded by a maximum serialized size that no registry or contract field carries, `claims.md` Q2D-C-03 claims it is enforced, and the `output_schema` every entry does carry is referenced by no normative rule.

**Five closed recently**, and

each changed what an implementer reads: **E-17** puts an `enum` coarsening
mapping in the requester's answer contract, superseding §3.2's old equality rule;
**E-16** moved the registry's JSON Schema profile into
[`scope.md`](../../spec/scope.md) §4.1, where an implementation built from
`spec/` alone will find it; and **E-25** settles that a policy modifier may not
coarsen an `enum` — a rule in
[`core-model.md`](../../spec/core-model.md) §3.2 now, rather than the
conservative position it was while the question was open. Writing E-25's reason
down raised two more, both now closed. **E-26** gave and gave `core-model.md` a new **§3.3**:
two narrowings of one dimension compose to their greatest lower bound — the
coarser value for a number or duration, the intersection for a range or a field
set — an empty result failing closed either way. **E-27** is closed too: §3.2's
four conditions admitted a coarsening onto a single label while
[`registry/validate.py`](../../registry/validate.py) rejected one and §3.2's own
`boolean` rationale agreed with the validator, so §3.2 gains a **fifth**
condition — at least two labels — and requires an `object` release to name at
least one detail field, which is the same rule reaching the same constant by the
other route. See
[`../open-escalations.md`](../open-escalations.md), which is where every
escalation is recorded and where a new one goes.

| # | Title | Stage | Status |
|---|---|---|---|
| [P-001](P-001-conformance-corpus.md) | Conformance corpus format and harness contract | 0 | **Ready for decomposition** |
| [P-002](P-002-message-envelope.md) | Message envelope and canonical structures | 1 | **Ready for decomposition** |
| [P-003](P-003-crypto-suites.md) | Cryptographic suites, key handling, downgrade policy | 1 | **Ready for decomposition** |
| [P-004](P-004-replay-idempotency.md) | Replay, expiry, idempotency | 1 | **Ready for decomposition** |
| [P-005](P-005-registry-client.md) | Registry client: pinning, resolution, fail-closed | 2 | **Ready for decomposition** |
| [P-006](P-006-request-validation.md) | Request validation and effective answer domain | 2 | **Ready for decomposition** — issue 4 blocked for an `object` carrying `maximum_cardinality` (E-28) |
| [P-007](P-007-policy-engine.md) | Policy engine contract and fail-closed invariants | 3 | **Ready for decomposition** |
| [P-008](P-008-capacity-accounting.md) | Disclosure-capacity accounting | 3 | **Ready for decomposition** |
| [P-009](P-009-denial-normalization.md) | Denial normalization | 3 | **Ready for decomposition** |
| [P-010](P-010-responder-pipeline.md) | Responder pipeline, predicate execution, output validation | 4 | **Ready for decomposition** — issue 8's serialized-size check blocked on E-28 |
| [P-011](P-011-receipts-audit.md) | Receipts and local audit | 4 | **Ready for decomposition** |
| [P-012](P-012-requester-runtime.md) | Requester runtime | 5 | **Ready for decomposition** |
| [P-013](P-013-https-binding.md) | Direct HTTPS binding and custodian daemon | 6 | **Ready for decomposition** |
| [P-014](P-014-identity-pairing.md) | Identity and the local pairing profile | 6 | **Ready for decomposition** |
| [P-015](P-015-escalation-lifecycle.md) | Escalation lifecycle | 7 | **Ready for decomposition** |
| [P-016](P-016-demonstration-adversarial.md) | Reference demonstration and adversarial suite | 8 | **Ready for decomposition** |

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
