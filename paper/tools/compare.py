#!/usr/bin/env python3
"""Compare two manuscript DOCX files paragraph by paragraph.

Used by `make repro` to prove the reconstructed pipeline still reproduces the
published Draft 0.2.1. Splits the report into body and bibliography because
they drift for different reasons: body drift means the pipeline is wrong,
bibliography drift means the CSL edition moved.

Usage:
    python3 tools/compare.py <reference.docx> <candidate.docx>
"""

from __future__ import annotations

import difflib
import html
import re
import sys
import zipfile
from pathlib import Path


def paragraphs(path: Path) -> list[tuple[str, str]]:
    body = zipfile.ZipFile(path).read("word/document.xml").decode("utf-8", "replace")
    out = []
    for para in re.findall(r"<w:p\b.*?</w:p>", body, re.S):
        text = html.unescape("".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", para)))
        style = re.search(r'<w:pStyle w:val="([^"]+)"', para)
        out.append((style.group(1) if style else "", text))
    return out


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    ref, cand = Path(argv[1]), Path(argv[2])
    a, b = paragraphs(ref), paragraphs(cand)

    print(f"reference: {ref.name}  ({len(a)} paragraphs)")
    print(f"candidate: {cand.name}  ({len(b)} paragraphs)")

    if len(a) != len(b):
        print(f"\nFAIL paragraph count differs: {len(a)} vs {len(b)}")
        return 1

    styles_match = [s for s, _ in a] == [s for s, _ in b]
    print(f"style sequence identical: {styles_match}")

    bib_start = next((i for i, (s, _) in enumerate(a) if s == "Bibliography"), len(a))
    body_diffs = [i for i in range(bib_start) if a[i][1] != b[i][1]]
    bib_diffs = [i for i in range(bib_start, len(a)) if a[i][1] != b[i][1]]

    print(f"\nbody          {bib_start - len(body_diffs)}/{bib_start} paragraphs identical")
    print(f"bibliography  {len(a) - bib_start - len(bib_diffs)}/{len(a) - bib_start} entries identical")

    for i in body_diffs[:5]:
        print(f"\n  body drift at paragraph {i} [{a[i][0]}]")
        for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a[i][1], b[i][1]).get_opcodes():
            if tag != "equal":
                print(f"    {tag:8} ref={a[i][1][i1:i2][:60]!r} cand={b[i][1][j1:j2][:60]!r}")

    if body_diffs or not styles_match:
        print(f"\nFAIL body text or styling drifted ({len(body_diffs)} paragraphs)")
        return 1
    if bib_diffs:
        print(f"\nPASS body reproduces exactly; {len(bib_diffs)} bibliography entries "
              f"differ (CSL edition variance -- see README)")
    else:
        print("\nPASS exact reproduction")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
