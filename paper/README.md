# Q2D technical report — build pipeline

Draft 0.2.1 was produced on another system and shipped without its build
tooling, so the manuscript could not be revised without losing the DOCX and PDF
that go with it. This directory reconstructs that pipeline from the artifacts
themselves.

```
src/          editable source — manuscript, bibliography, CSL, figures, template
tools/        build and verification scripts
build/        generated, disposable          (gitignored)
dist/         assembled source packages      (gitignored)
Q2D_Technical_Report_Draft_v0.2.1_Source_Package/   the published 0.2.1 release
```

The 0.2.1 package directory is a released, checksummed artifact. Do not edit it;
build new drafts and let `make dist` assemble a new package beside it.

## Requirements

| Tool | Used for | Notes |
|---|---|---|
| pandoc | Markdown → DOCX, citation processing | 3.10 verified |
| LibreOffice (`soffice`) | DOCX → tagged PDF | 26.2 verified; supplies the tagging and lossless-image export |
| Python 3 | figures and verification | `make venv` creates `.venv` from `requirements.txt` |

## Usage

```sh
make                      # build DOCX + PDF for $(DRAFT) and run the deposit checks
make DRAFT=0.3            # build a different draft
make dist                 # assemble a checksummed, zipped source package
make repro                # rebuild published 0.2.1 and diff against the shipped DOCX
make figures              # regenerate query_sequence.png (see caveat below)
make clean                # drop build/
```

Variables: `DRAFT` (default `0.2.2`), `PROTOCOL`, `CSL`, `PAGES` (asserts an
expected page count when set).

## Bumping the draft number

The version appears in three places. `make` handles the second and third; you
edit the first:

1. `src/manuscript.md` — the `date:` and `subject:` YAML fields.
2. The running header, stamped into the template by `tools/stamp_reference.py`.
3. Output filenames, derived from `DRAFT`.

`tools/verify.py` fails the build if these disagree. That check exists because
the shipped 0.2.1 DOCX carries a `docProps/custom.xml` still claiming "Draft
0.2" and a v0.2 `.bib` filename — stale metadata that rode along from an earlier
build and would have gone into the deposit unnoticed.

## How the pipeline was recovered

Nothing here was guessed; each choice was read off the shipped artifacts.

- **pandoc as the DOCX writer** — `docProps/custom.xml` carries `link-citations`
  and `reference-section-title` as custom document properties, which is how
  pandoc emits YAML metadata it does not otherwise recognise.
- **A custom `reference.docx`** — page margins are 2 cm left/right and 0.7 in
  bottom, not pandoc's 1 in default, and the file carries three header/footer
  parts with a distinct first page. `tools/make_reference_docx.py` recovers that
  template from the shipped DOCX by dropping the body, the images and the stale
  custom properties, and keeping the styles, theme, numbering and header/footer
  parts. Result: 14 KB instead of 1.2 MB.
- **LibreOffice as the PDF writer** — the shipped PDF is tagged, unencrypted,
  PDF-1.7, and every image stream is `/FlateDecode` with no `/DCTDecode`. That
  is exactly LibreOffice's `UseTaggedPDF` + `UseLosslessCompression` +
  `ReduceImageResolution=false` export combination.
- **No TOC and no section numbering** — the shipped DOCX contains no field
  codes and no numbered headings, so neither `--toc` nor `--number-sections`
  is used. The `{.unnumbered}` markers in the manuscript are inert but harmless.

## Reproduction status

`make repro` rebuilds Draft 0.2.1 from source and diffs it against the shipped
DOCX:

```
style sequence identical: True
body          1056/1056 paragraphs identical
bibliography  1/35 entries identical
```

**Body text reproduces exactly.** The rebuilt PDF is likewise 43 pages, tagged,
unencrypted, PDF-1.7, with zero `/DCTDecode` streams and all three figures
byte-identical to their standalone PNGs.

Three known sources of variance, none affecting body text:

1. **Bibliography rendering (34 of 35 entries).** The original build's CSL
   snapshot is not recoverable without knowing which pandoc version produced it.
   Chicago 17th edition is pinned in `src/` because it reproduces every in-text
   citation exactly — 0 body-paragraph diffs — leaving only title-quoting
   differences in the reference list. Chicago 18th (current CSL master) drifts
   further, changing `et al.` thresholds in the body. Pinning the file matters
   more than which edition: an unpinned `--csl` re-renders the bibliography
   whenever pandoc updates. Override with `make CSL=...`.
2. **Figures.** `make figures` regenerates `query_sequence.png` from
   `make_sequence_figure.py`. Current matplotlib produces the same 2858×1773
   image but not the same bytes, which would cascade through the DOCX, the PDF
   and every checksum. The shipped PNG is therefore treated as a source asset
   and regeneration is opt-in.
3. **Fonts.** The newer LibreOffice embeds 10 font files where the original
   embedded 9. Cosmetic.

## What `make verify` checks

Each item is an assertion the 0.2.1 release notes made in prose:

- all three figures are genuine PNGs;
- each embedded DOCX image is byte-identical to its standalone PNG;
- the running header, custom properties and core properties all state the
  current draft, and no stale draft number survives anywhere;
- citations all resolved — no `[@key]` or `???` left in the output;
- the PDF is tagged (`/StructTreeRoot`, `/MarkInfo /Marked true`), unencrypted,
  has embedded fonts, extractable text, and the expected page count;
- no figure stream uses JPEG compression (`/DCTDecode` count is zero);
- for a package, `SHA256SUMS.txt` covers every file and every digest matches.

`make dist` generates `SHA256SUMS.txt` only after all other files are in place,
then re-verifies the assembled package and tests the zip.
