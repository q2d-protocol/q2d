# Versioning and release tags

This repository holds artifacts that version independently: a protocol
specification, a technical report, and two reference implementations. They do
not move together, and a single tag series cannot express that.

## Tag scheme

| Tag | Artifact | Example |
|---|---|---|
| `vX.Y.Z` | **Implementation release** — the Rust crate and the Go module, released together at the same version | `v0.1.0` |
| `spec/vX.Y` | Protocol specification version | `spec/v0.1` |
| `report/vX.Y.Z` | Technical report draft | `report/v0.2.2` |

### Why bare tags mean the implementation

Not a stylistic choice. Go's module resolution requires a tag of the form
`vX.Y.Z` at the repository root for a root-level module, and the Go module path
here **is** `q2d.dev` at the root. Prefixing every tag would leave the Go module
resolvable only through pseudo-versions. Bare tags are therefore reserved for
the implementation, and everything else is prefixed.

### Why the Rust crate and the Go module share a version

The two implementations are developed in lockstep against shared test vectors.
A divergence between them is a finding — usually a specification ambiguity —
rather than a normal state to be managed with separate version lines. Releasing
them at one version makes that lockstep visible and makes a mismatch a
conspicuous error rather than a routine skew.

The Cargo and Go module versions therefore track `vX.Y.Z` exactly.

### Independent version lines

| Line | Advances when |
|---|---|
| Protocol specification | Wire semantics or normative requirements change |
| Technical report draft | The manuscript is revised |
| Implementation | Code is released |

The report and the protocol are numbered independently and always have been:
Technical Report Draft 0.2.2 describes Q2D protocol version **0.1**. Any
coincidence between these numbers is accidental and should not be relied on.

A query and receipt bind the core protocol version, predicate version, registry
digest, and assurance profile, so a later code or registry update cannot
reinterpret an earlier exchange. See
[`../spec/core-model.md`](../spec/core-model.md) §8.

## Published packages

| Registry | Name | Tracks |
|---|---|---|
| crates.io | `q2d` | `vX.Y.Z` |
| Go modules | `q2d.dev` | `vX.Y.Z` |
| npm | `@q2d/spec` | `spec/vX.Y` |

Registry versions are permanent and never reusable. crates.io in particular
does not permit republishing a version, so a mistaken release is corrected by
publishing a new version, not by replacing one.

## Archived releases

Technical report drafts are deposited with a DOI. The deposit is the citable
artifact; the git tag is the build input. A report tag is created *before* the
deposit, so the DOI and the tag refer to identical bytes.

Each deposited draft keeps its own version-specific DOI. Cite a specific draft
when the claim being cited is version-sensitive — which, for a pre-release
protocol, is usually.

## Known divergences from the deposited report

The specification moves faster than the report. Where the two disagree,
[`../spec/core-model.md`](../spec/core-model.md) governs — it says so in its own
header — but a reader arriving from the DOI has no way to know which passages
have moved. This table is that record.

`paper/src/manuscript.md` is **not** amended as these accumulate. It is the build
input the `make repro` gate rebuilds Draft 0.2.1 from and diffs against the
published DOCX; editing it would break the reproducibility check that makes the
deposit verifiable. The corrections are applied in one pass when a new draft is
opened, and this table is the worklist for that pass.

The first row is the one that matters, and it is a **security** divergence rather
than an editorial one.

| Deposited text | Current specification | Decided in |
|---|---|---|
| §*Answer contract*: *"The requester may ask for a **subset** or coarser version of the registered domain."* | **Subsetting is prohibited.** A requester may only coarsen. A subset request turns an out-of-domain result into a free oracle: asking a boolean predicate with a requested domain of `[true]` returns `true` for a true result and a denial for a false one, revealing the answer either way while debiting nothing. Permitting subsets defeats Q2D-C-09 for every subsettable predicate ([`../spec/core-model.md`](../spec/core-model.md) §2.5) | The P-006 subsetting escalation |
| The direct HTTPS binding lists `GET /.well-known/q2d/predicates/{id}/{version}` | That endpoint is removed. Serving a registry entry unauthenticated reveals which predicates a custodian supports, and defeats the §2.4.1 entry-digest comparison, since a requester fetching the entry from the custodian it is about to query always declares a matching digest. Registry distribution stays out of band | [`open-escalations.md`](open-escalations.md) E-06 |
| The effective answer domain is described as the *intersection* of registry entry, requester contract, and policy modifiers | It is a **narrowing composition**. Coarsenings of different granularity are not sets that intersect ([`../spec/core-model.md`](../spec/core-model.md) §3) | E-12 |
| Appendix C item 5 — *whether denied and escalated outcomes affect the capacity budget* — is open | Decided: they do not. A separate, **required** rate limit bounds the probing they would otherwise permit, and its rejections normalize like any other cause ([`../spec/core-model.md`](../spec/core-model.md) §9.1) | E-01 |
| Appendix C item 1 — *exact core-versus-profile boundary for identity and delegation* — is open | Decided: [`../spec/core-model.md`](../spec/core-model.md) §2.3 defines the three interfaces. Only *which profile, if any, is mandatory to implement* remains open | E-10 |
| Appendix C item 12 lists grant lifetime and revocation as open, and says nothing about multiplicity | Multiplicity is decided: a grant is **single-use** ([`../spec/core-model.md`](../spec/core-model.md) §5.3). The field list and lifetime remain open | E-02 |
| The `escalate` outcome carries no receipt | An explicit `escalate` carries the reduced receipt with `decision_class: escalate`; an opaque escalation carries the ordinary deny receipt, so its normalization survives into the evidence | E-03 |
| §*Idempotency*: a changed purpose, sink set, public context, predicate version, or answer contract creates a distinct request | Unchanged, but the clause is now stated as a **floor** on whatever field list the approval-scope digest settles on, not as a description of the current one ([`../spec/core-model.md`](../spec/core-model.md) §7) | E-04 |
| No requester-side processing order is given | [`../spec/core-model.md`](../spec/core-model.md) §4.1 makes one normative | E-14 |
