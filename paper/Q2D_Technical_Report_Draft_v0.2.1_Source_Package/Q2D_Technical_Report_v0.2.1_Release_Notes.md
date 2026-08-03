# Q2D Technical Report Draft 0.2.1 — Release-Candidate Notes

**Report draft:** 0.2.1  
**Protocol described:** Q2D 0.1 (pre-release)  
**Date:** July 2026

Draft 0.2.1 is a narrow release-candidate revision of Draft 0.2. It does not change Q2D's architecture, claims, scope, or publication sequence. It resolves one protocol-semantics ambiguity identified in final review, clarifies the independent version lines, and rebuilds the source package from verified lossless figure assets with fresh checksums.

## 1. Opaque escalation and idempotency

The manuscript now defines a single coherent lifecycle:

1. The original opaque-escalation query returns a normalized external outcome.
2. Replaying that same signed query identifier and nonce always returns the same cached outcome and never becomes an answer after approval.
3. If the authority approves, the custodian records a time-bounded grant keyed to an **approval-scope digest**. The digest covers the policy-relevant requester, predicate, answer contract, purpose, recipient, sinks, and public-context commitment, while excluding nonce and request-instance timestamps.
4. The requester can submit a fresh signed query with a new identifier and nonce but the same approval scope.
5. The responder revalidates registry state, delegation, policy, freshness, disclosure budget, and current protected data before answering, then issues a new receipt.
6. The resulting unavailable-to-answer transition is explicitly named as a residual timing and state oracle.
7. A binding may define authenticated push delivery, but it may not silently mutate the cached result of an identical retry.

The rule is stated in **Response types / Escalate**, cross-referenced in **Replay, idempotency, and retries**, and reflected in **Denial normalization**. Appendix C now records the exact approval-scope fields, grant lifetime and revocation, and binding-specific delivery semantics as work for the normative specification.

## 2. Version-line clarification

The title page now states that report drafts and protocol versions are numbered independently:

> Technical Report Draft 0.2.1 describes the pre-release Q2D protocol version 0.1.

The public-release sequence now names the intended deposit consistently as **Technical Report Draft 0.2.1, describing Q2D protocol version 0.1**.

## 3. Packaging verification

The release package was rebuilt after the final edits and after a PDF-internal image-encoding audit.

- All three standalone figure files are genuine PNG files, verified by the operating-system file inspector and Pillow.
- `query_sequence.png` was regenerated directly from the included Matplotlib script.
- Each standalone figure is byte-identical to the corresponding image embedded in the DOCX.
- The deposit PDF was exported with **lossless image compression** and no image-resolution reduction.
- Inspection of the PDF image objects confirms that all three color figure streams use `/FlateDecode`; no figure uses `/DCTDecode`/JPEG compression.
- The PDF remains tagged, contains 43 pages, is unencrypted, opens successfully, and embeds all document fonts.
- Text extracted from the rebuilt PDF is byte-for-byte identical to text extracted from the prior 0.2.1 export; rendered differences are confined to the two figures that were previously JPEG-compressed.
- `SHA256SUMS.txt` was generated only after final package assembly.
- `sha256sum -c SHA256SUMS.txt` passes for every listed artifact.
- The ZIP archive passes an integrity test after creation.

## 4. Release recommendation

Draft 0.2.1 is suitable for deposit as an openly labeled **experimental design report and defensive technical disclosure**. It should not be described as a completed or empirically evaluated security/privacy system. The next substantive project artifact remains the specification spine and then the normative core specification.
