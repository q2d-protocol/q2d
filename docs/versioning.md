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
