# Q2D — Query-to-Data

**A transport-neutral protocol for policy-bound, least-disclosure answers over protected data.**

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.21777305.svg)](https://doi.org/10.5281/zenodo.21777305)

> ⚠️ **Pre-release.** The technical report is published; the specification spine
> is in progress and the reference implementation is not written. Nothing is
> installable or usable yet — the packages reserve the name.

## Technical report

**[Query-to-Data: Policy-Bound, Least-Disclosure Answers for AI Agents](https://doi.org/10.5281/zenodo.21777306)**
— Technical Report Draft 0.2.2, describing Q2D protocol version 0.1.

An experimental design report and defensive technical disclosure. Sections 12
and 13 are written prospectively; no Phase 1 conformance or performance result
is claimed.

| | DOI |
|---|---|
| This draft (cite this) | [10.5281/zenodo.21777306](https://doi.org/10.5281/zenodo.21777306) |
| All versions | [10.5281/zenodo.21777305](https://doi.org/10.5281/zenodo.21777305) |

Cite a specific draft. The protocol is pre-release and its claims are
version-sensitive.

## What it is

Agents are routinely given record- or document-level access to answer questions
whose legitimate output is a boolean, an enum, or a small bounded result. Q2D
inverts that: the question travels to the data instead of the data travelling to
the question.

A requester submits a signed, typed **answer contract** — the question, its
purpose, the intended recipient, the permitted sinks, and the maximum response
domain — before any evaluation happens. A participating custodian evaluates the
query locally under the applicable policy and returns a bounded, authenticated
answer plus a disclosure receipt.

## What it does not claim

Q2D does not make a released answer retractable, prove the truth of self-asserted
inputs, prevent all inference from repeated answers, or independently establish
legal compliance.

## Status

Pre-release. Specification and reference implementation in development.

- Website: https://q2d.dev
- Source and specification: https://github.com/q2d-protocol

## Licensing

| What | License | File |
|---|---|---|
| Reference implementation, schemas, conformance test vectors | Apache-2.0 | [`LICENSE`](LICENSE) |
| Technical report and specification prose | CC BY 4.0 | [`LICENSE-DOCS`](LICENSE-DOCS) |

**Patents.** The Q2D project holds no patents and has filed no patent
applications on the mechanisms described here. It covenants not to assert any
patent it may later acquire against any implementation conforming to a
published Q2D specification. Note that CC BY 4.0 grants no patent rights of its
own — this covenant is what closes that gap for the specification prose.

**Name.** See [`TRADEMARKS.md`](TRADEMARKS.md) for how the Q2D name may be used.
