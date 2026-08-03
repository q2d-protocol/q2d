#!/usr/bin/env python3
"""Derive a pandoc --reference-doc template from a built manuscript DOCX.

The Draft 0.2.1 package was produced on another system and shipped no build
pipeline. Its DOCX, however, still carries the styling that pipeline used:
Liberation font bindings, 2 cm / 0.7 in page margins, and three header/footer
parts with a distinct first page. This script recovers that styling as a
reusable template so later drafts render identically.

What it keeps: styles, theme, numbering, settings, fontTable, footnotes,
comments, and the header/footer parts, plus the sectPr that binds them.

What it drops:
  * word/media/*        - body images; pandoc adds its own per build.
  * body content        - replaced by an empty paragraph.
  * docProps/custom.xml - the shipped file carries stale 0.2-era values
                          ("Draft 0.2", a v0.2 .bib filename). Pandoc merges
                          the reference doc's custom properties into its
                          output, so keeping it would propagate that staleness
                          into every future build. Dropping it lets pandoc
                          write custom properties from manuscript metadata
                          alone.

Usage:
    python3 tools/make_reference_docx.py <source.docx> <out-reference.docx>
"""

from __future__ import annotations

import re
import shutil
import sys
import zipfile
from pathlib import Path

# Relationship ids rId1-rId11 are the template parts in the shipped DOCX;
# image relationships (rId25/39/64) belong to the body and must not survive.
DROP_PREFIXES = ("word/media/",)
DROP_EXACT = {"docProps/custom.xml"}

EMPTY_DOCUMENT = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" \
xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<w:body><w:p/>{sectpr}</w:body></w:document>"""


def extract_sectpr(document_xml: str) -> str:
    match = re.search(r"<w:sectPr\b.*?</w:sectPr>", document_xml, re.S)
    if not match:
        raise SystemExit("no <w:sectPr> found; cannot recover page setup")
    return match.group(0)


def strip_image_rels(rels_xml: str) -> str:
    return re.sub(
        r'<Relationship[^>]*Type="[^"]*/image"[^>]*/>',
        "",
        rels_xml,
    )


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2

    source, target = Path(argv[1]), Path(argv[2])
    if not source.is_file():
        raise SystemExit(f"source not found: {source}")

    with zipfile.ZipFile(source) as zin:
        document_xml = zin.read("word/document.xml").decode("utf-8")
        sectpr = extract_sectpr(document_xml)

        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(".tmp")
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                name = item.filename
                if name in DROP_EXACT or name.startswith(DROP_PREFIXES):
                    continue
                if name == "word/document.xml":
                    zout.writestr(name, EMPTY_DOCUMENT.format(sectpr=sectpr))
                elif name == "word/_rels/document.xml.rels":
                    zout.writestr(name, strip_image_rels(zin.read(name).decode("utf-8")))
                else:
                    zout.writestr(item, zin.read(name))
        shutil.move(tmp, target)

    with zipfile.ZipFile(target) as check:
        parts = check.namelist()
    print(f"wrote {target} ({target.stat().st_size} bytes, {len(parts)} parts)")
    print("  page setup:", re.sub(r"<w:(header|footer)Reference[^/]*/>", "", sectpr))
    for part in ("word/styles.xml", "word/header1.xml", "word/footer1.xml", "word/footer2.xml"):
        print(f"  {'kept  ' if part in parts else 'MISSING'} {part}")
    assert not any(p.startswith("word/media/") for p in parts), "media leaked into template"
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
