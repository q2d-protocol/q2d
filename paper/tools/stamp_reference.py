#!/usr/bin/env python3
"""Stamp the draft number into the reference.docx running header.

The recovered template carries "Q2D Technical Report | Draft 0.2.1" as literal
text in word/header1.xml. Left alone it would silently print the wrong draft
number on all 43 pages of every later build -- exactly the failure that left
Draft 0.2.1 shipping a docProps/custom.xml still claiming "Draft 0.2".

Usage:
    python3 tools/stamp_reference.py <in.docx> <out.docx> <draft-version>
"""

from __future__ import annotations

import re
import shutil
import sys
import zipfile
from pathlib import Path

HEADER_PART = "word/header1.xml"
DRAFT_RE = re.compile(r"(Draft\s+)\d+(?:\.\d+)*")


def main(argv: list[str]) -> int:
    if len(argv) != 4:
        print(__doc__, file=sys.stderr)
        return 2

    source, target, draft = Path(argv[1]), Path(argv[2]), argv[3]
    with zipfile.ZipFile(source) as zin:
        if HEADER_PART not in zin.namelist():
            raise SystemExit(f"{source} has no {HEADER_PART}")
        header = zin.read(HEADER_PART).decode("utf-8")
        stamped, count = DRAFT_RE.subn(rf"\g<1>{draft}", header)
        if count == 0:
            raise SystemExit(f"no 'Draft <n>' text found in {HEADER_PART}; header not stamped")

        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(".tmp")
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data = stamped.encode("utf-8") if item.filename == HEADER_PART else zin.read(item.filename)
                zout.writestr(item, data)
        shutil.move(tmp, target)

    shown = re.search(r"<w:t[^>]*>([^<]*Draft[^<]*)</w:t>", stamped)
    print(f"stamped header -> {shown.group(1) if shown else draft}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
