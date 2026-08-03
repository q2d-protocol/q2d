# Q2D Technical Report Draft 0.2.2 — Release Notes

**Report draft:** 0.2.2
**Protocol described:** Q2D 0.1 (pre-release)
**Date:** August 2026

Draft 0.2.2 resolves the last open blocker to public deposit and repairs two
defects in the 0.2.1 package. It does not change Q2D's architecture, claims,
scope, threat model, or publication sequence. No new protocol semantics are
introduced.

## 1. Document license and patent posture

Appendix C of Draft 0.2.1 listed "document license for the specification and
report" as an unresolved drafting decision, and the 0.2.1 package README asked
that it be settled before public deposit. It is now settled and stated on the
title page:

- The report and the Q2D specification prose are licensed under the **Creative
  Commons Attribution 4.0 International License (CC BY 4.0)**.
- Reference implementation code, schemas, and conformance test vectors remain
  under **Apache-2.0**.
- The project states an explicit **patent non-assertion covenant**: it holds no
  patents and has filed no patent applications on these mechanisms, and will not
  assert any patent it may later acquire against a conforming implementation.

The covenant is stated separately because CC BY 4.0 grants no patent rights of
its own. Without it, an implementer reading a CC BY specification cannot tell
that the project's no-patents position exists.

The item is struck from Appendix C, which renumbers from thirteen entries to
twelve. No other Appendix C item changed.

## 2. Version-line and date corrections

The title page, the current-status section, and the running header now read
August 2026 and Draft 0.2.2. Report drafts and protocol versions remain
independently numbered: **Draft 0.2.2 describes Q2D protocol version 0.1.**

## 3. Source completeness

The 0.2.1 manuscript could not reproduce its own document metadata: the shipped
DOCX carried `dc:subject`, `dc:description`, and language core properties for
which the Markdown source had no corresponding fields. Anyone rebuilding from
the published source would have produced a file with weaker metadata than the
published one.

The manuscript front matter now carries `subject`, `description`, and
`keywords`, so the source is self-sufficient. The keyword list matches the
abstract's.

The title page also carries the author's affiliation and ORCID iD. The
affiliation is **independent researcher**: this work was not produced under the
auspices of any institution, and naming one would imply backing that does not
exist. The ORCID iD makes the author identity resolvable across this and any
later deposit.

## 4. Packaging defects fixed

Two defects in the 0.2.1 package are corrected:

- The 0.2.1 DOCX shipped a `docProps/custom.xml` still naming **"Draft 0.2"**
  and a **v0.2** bibliography filename — stale metadata carried forward from an
  earlier build. The template used for 0.2.2 no longer propagates document
  properties from previous builds.
- The draft number in the running header was fixed text. It is now stamped at
  build time from a single source, so a header cannot disagree with the filename
  and title page again.

## 5. Build reproducibility

Draft 0.2.1 was produced on a system that shipped no build tooling, which meant
the manuscript could not be revised without losing the DOCX and PDF paired with
it. The pipeline has been reconstructed from the shipped artifacts and is now
part of the repository:

- pandoc renders the DOCX against a page-layout template recovered from the
  0.2.1 file; LibreOffice exports the tagged PDF with lossless image compression
  and image-resolution reduction disabled.
- The citation style is pinned to a specific vendored CSL file, so bibliography
  rendering no longer changes when the toolchain updates.
- Rebuilding Draft 0.2.1 from source reproduces its body text exactly: 1056 of
  1056 body paragraphs and the full paragraph-style sequence are identical.
  Differences are confined to reference-list formatting, where the original
  build's CSL snapshot is not recoverable.

## 6. Packaging verification

Every property the Draft 0.2.1 notes asserted in prose is now an executable
check that must pass before a package can be assembled:

- All three standalone figures are genuine PNG files.
- Each figure is byte-identical to the corresponding image embedded in the DOCX.
- The PDF is 43 pages, tagged, unencrypted, with all document fonts embedded and
  text extractable.
- Every figure stream uses `/FlateDecode`. No figure uses `/DCTDecode`/JPEG
  compression, and image-resolution reduction was disabled at export.
- The running header, custom properties, core properties, and filename all state
  the same draft number.
- No citation is left unresolved in the rendered output.
- `SHA256SUMS.txt` is generated only after final package assembly, covers every
  file in the package, and verifies.
- The ZIP archive passes an integrity test after creation.

## 7. Responder terminology made precise

Draft 0.2.1 used "custodian runtime" and "computation executor" for overlapping
responsibilities, and in one case for the same referent inside a single threat-
table row. The trust statements consequently disagreed with each other about
which component signs a response and which one Phase 1 trusts.

The terms are now used at distinct levels, and the roles section states the
relationship explicitly:

- the **responder** is the protocol role opposite the requester, and normative
  requirements address it;
- the **custodian runtime** is the deployed software implementing that role,
  owning authentication, delegation, registry and domain validation, policy
  invocation, budget accounting, and receipt issuance;
- the **computation executor** is the narrower role that accesses private input
  and signs the result.

In version 0.1 the custodian runtime holds the executor role, so the two
coincide in deployment. They are distinguished because the assurance profiles
work by relocating the executor — to a credential holder, a proof system, or a
measured environment — while the responder lifecycle stays in place. Statements
about Phase 1 trust therefore name the computation executor.

No claim, guarantee, or protocol behaviour changes. The affected passages are
the role table, the trust assumptions, the threat-actor discussion, the threat
analysis table, the input-provenance discussion, and the limitations section.

## 8. Release recommendation

Draft 0.2.2 is suitable for deposit as an openly labelled **experimental design
report and defensive technical disclosure**. It must not be described as a
completed or empirically evaluated security or privacy system. Sections 12 and
13 remain prospective, and no Phase 1 conformance or performance result is
claimed.

The next substantive project artifact remains the specification spine, then the
normative core specification.
