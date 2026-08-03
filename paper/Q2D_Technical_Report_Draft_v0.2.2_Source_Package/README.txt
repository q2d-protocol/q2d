Q2D TECHNICAL REPORT DRAFT 0.2.2 — SOURCE PACKAGE

Title:
  Query-to-Data: Policy-Bound, Least-Disclosure Answers for AI Agents

Version lines:
  Report draft: 0.2.2
  Protocol described: Q2D 0.1 (pre-release)
  These version lines are independent.

Status:
  Experimental design report and protocol proposal.
  Not an official MCP or A2A specification.
  No completed Phase 1 implementation or empirical result is claimed.

Included:
  - Formatted DOCX manuscript
  - Fixed-layout, tagged PDF manuscript with losslessly embedded figures
  - Editable Markdown source
  - BibTeX bibliography
  - Three publication figures in genuine PNG format
  - Figure 3 Matplotlib generation script
  - Draft 0.2.2 release notes
  - SHA-256 checksums generated after final package assembly

PDF verification:
  All three color figure streams use /FlateDecode. No figure is stored with
  /DCTDecode/JPEG compression. Image-resolution reduction was disabled at export.
  The PDF is tagged, unencrypted, 43 pages, and embeds all document fonts.

Checksum verification:
  From the package root, run:

    sha256sum -c SHA256SUMS.txt

  Every listed file should report OK.

Licensing:
  This report and the Q2D specification prose are licensed under the Creative
  Commons Attribution 4.0 International License (CC BY 4.0).
  https://creativecommons.org/licenses/by/4.0/

  Reference implementation code, schemas, and conformance test vectors are
  licensed under Apache-2.0.

  The Q2D project holds no patents and has filed no patent applications on the
  mechanisms described here, and covenants not to assert any patent it may later
  acquire against any implementation conforming to a published Q2D
  specification. CC BY 4.0 grants no patent rights of its own; this covenant is
  stated separately for that reason.

Reproducing this package:
  The build pipeline is published with the project source. From the paper
  directory:

    make DRAFT=0.2.2 dist

  Requires pandoc, LibreOffice, and Python 3. See paper/README.md for the
  toolchain, the recovered page-layout template, the pinned citation style, and
  known sources of build variance.
