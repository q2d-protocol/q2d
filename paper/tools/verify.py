#!/usr/bin/env python3
"""Verify a built Q2D technical report against the deposit checks.

Implements, as executable assertions, every property the Draft 0.2.1 release
notes claimed by hand. A build that passes may be deposited; a build that fails
must not be.

Usage:
    python3 tools/verify.py --draft 0.2.2 --build build --src src
    python3 tools/verify.py --draft 0.2.1 --package <dir>   # check a source package
"""

from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
import zipfile
from pathlib import Path

from PIL import Image
from pypdf import PdfReader

FAILURES: list[str] = []
CHECKS = 0


def check(condition: bool, label: str, detail: str = "") -> bool:
    global CHECKS
    CHECKS += 1
    if condition:
        print(f"  ok    {label}" + (f"  [{detail}]" if detail else ""))
    else:
        print(f"  FAIL  {label}" + (f"  [{detail}]" if detail else ""))
        FAILURES.append(label)
    return condition


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def docx_text(path: Path) -> list[str]:
    import html

    body = zipfile.ZipFile(path).read("word/document.xml").decode("utf-8", "replace")
    return [
        html.unescape("".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", p)))
        for p in re.findall(r"<w:p\b.*?</w:p>", body, re.S)
    ]


def verify_figures(figures: Path) -> dict[str, str]:
    print("\nfigures")
    digests: dict[str, str] = {}
    pngs = sorted(figures.glob("*.png"))
    check(len(pngs) == 3, "three figure files present", f"{len(pngs)} found")
    for png in pngs:
        try:
            with Image.open(png) as im:
                fmt, size = im.format, im.size
            ok = fmt == "PNG"
        except Exception as exc:  # noqa: BLE001
            ok, fmt, size = False, str(exc), None
        check(ok, f"{png.name} is a genuine PNG", f"{fmt} {size}")
        digests[png.name] = sha256(png)
    return digests


def verify_docx(docx: Path, draft: str, figure_digests: dict[str, str]) -> None:
    print("\ndocx")
    if not check(docx.is_file(), f"{docx.name} exists"):
        return
    z = zipfile.ZipFile(docx)
    names = z.namelist()

    media = {n: hashlib.sha256(z.read(n)).hexdigest() for n in names if n.startswith("word/media/")}
    check(len(media) == 3, "three images embedded", f"{len(media)}")
    embedded = set(media.values())
    for name, digest in figure_digests.items():
        check(digest in embedded, f"embedded image byte-identical to {name}")

    header = z.read("word/header1.xml").decode("utf-8") if "word/header1.xml" in names else ""
    check(f"Draft {draft}" in header, f"running header says Draft {draft}",
          (re.search(r"<w:t[^>]*>([^<]*Draft[^<]*)</w:t>", header) or [None, "?"])[1])

    custom = z.read("docProps/custom.xml").decode("utf-8") if "docProps/custom.xml" in names else ""
    stale = re.findall(r"Draft (\d+(?:\.\d+)*)", custom)
    check(all(s == draft for s in stale), "no stale draft number in custom properties",
          ",".join(stale) or "none")

    core = z.read("docProps/core.xml").decode("utf-8") if "docProps/core.xml" in names else ""
    check(draft in core, f"core properties reference {draft}")

    paras = docx_text(docx)
    check(len(paras) > 900, "document body populated", f"{len(paras)} paragraphs")
    bib = [p for p in paras if p.strip()]
    check(any("References" == p.strip() for p in paras), "References section rendered")
    unresolved = [p for p in paras if "???" in p or "[@" in p]
    check(not unresolved, "no unresolved citations", f"{len(unresolved)} found")


def verify_pdf(pdf: Path, expect_pages: int | None) -> None:
    print("\npdf")
    if not check(pdf.is_file(), f"{pdf.name} exists"):
        return
    raw = pdf.read_bytes()
    reader = PdfReader(str(pdf))
    root = reader.trailer["/Root"]

    check(raw[:8].startswith(b"%PDF-1."), "PDF header present", raw[:8].decode("latin1").strip())
    pages = len(reader.pages)
    if expect_pages:
        check(pages == expect_pages, f"page count is {expect_pages}", str(pages))
    else:
        check(pages > 0, "has pages", str(pages))
    check(not reader.is_encrypted, "not encrypted")
    check("/StructTreeRoot" in root, "tagged (StructTreeRoot present)")
    check(bool((root.get("/MarkInfo") or {}).get("/Marked")), "MarkInfo /Marked true")

    dct = raw.count(b"/DCTDecode")
    check(dct == 0, "no JPEG-compressed figure streams (/DCTDecode)", f"{dct}")
    check(raw.count(b"/FlateDecode") > 0, "streams use /FlateDecode", str(raw.count(b"/FlateDecode")))
    check(raw.count(b"/FontFile") > 0, "fonts embedded", f"{raw.count(b'/FontFile')} font files")

    text = "".join((page.extract_text() or "") for page in reader.pages[:3])
    check(len(text.strip()) > 500, "text extractable from first pages", f"{len(text)} chars")


def verify_manuscript(manuscript: Path, draft: str) -> None:
    print("\nmanuscript source")
    if not check(manuscript.is_file(), f"{manuscript.name} exists"):
        return
    text = manuscript.read_text(encoding="utf-8")
    head = text[:1500]
    date = re.search(r'^date:\s*"(.*)"', head, re.M)
    check(bool(date) and draft in date.group(1),
          f"YAML date states Draft {draft}", date.group(1) if date else "no date field")

    # The manuscript speaks only about itself, so every draft number in it must be
    # the current one. Draft 0.2.2 shipped review copies naming 0.2.1 in the
    # versioning note and the public-release sequence; both read as correct prose.
    stale = sorted({v for v in re.findall(r"Draft\s+v?(\d+\.\d+(?:\.\d+)?)", text)
                    if v != draft})
    check(not stale, "no stale draft number anywhere in the manuscript",
          ", ".join(f"Draft {v}" for v in stale))


def verify_package_prose(package: Path, src: Path | None, draft: str) -> None:
    """Guard the two hand-written package files against version staleness.

    They are per-release prose, so they cannot be generated -- but shipping the
    previous release's notes inside a new package is a silent, plausible
    failure. Draft 0.2.1 shipped stale metadata for exactly this reason.
    """
    print("\npackage prose")
    candidates = [
        ("README.txt", package / "README.txt" if package else None,
         (src / "package" / "README.txt") if src else None),
        ("release notes", package / f"Q2D_Technical_Report_v{draft}_Release_Notes.md" if package else None,
         (src / "package" / "release-notes.md") if src else None),
    ]
    for label, packaged, source in candidates:
        path = packaged if packaged and packaged.is_file() else source
        if path is None or not path.is_file():
            check(False, f"{label} present", str(packaged or source))
            continue
        # Only the header block is checked. Release notes legitimately cite
        # earlier drafts in the body when describing what changed; a wrong
        # version in the title or the "Report draft:" line is the actual defect.
        header = "\n".join(path.read_text(encoding="utf-8", errors="replace").splitlines()[:12])
        declared = set(re.findall(r"(?:Draft|Report draft:)\s+v?(\d+\.\d+(?:\.\d+)?)", header))
        check(declared == {draft}, f"{label} header declares Draft {draft}",
              ",".join(sorted(declared)) or "none found in first 12 lines")


def verify_checksums(package: Path) -> None:
    print("\nchecksums")
    sums = package / "SHA256SUMS.txt"
    if not check(sums.is_file(), "SHA256SUMS.txt present"):
        return
    listed = 0
    bad = []
    for line in sums.read_text().splitlines():
        if not line.strip():
            continue
        digest, _, name = line.partition("  ")
        target = package / name.strip().lstrip("./")
        listed += 1
        if not target.is_file() or sha256(target) != digest.strip():
            bad.append(name.strip())
    check(not bad, f"all {listed} listed files match their digest", ", ".join(bad) or "")
    tracked = {line.split("  ", 1)[1].strip().lstrip("./")
               for line in sums.read_text().splitlines() if line.strip()}
    present = {str(p.relative_to(package)) for p in package.rglob("*")
               if p.is_file() and p.name != "SHA256SUMS.txt"}
    check(present <= tracked, "no package file missing from SHA256SUMS.txt",
          ", ".join(sorted(present - tracked)) or "")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--draft", required=True)
    ap.add_argument("--build", type=Path)
    ap.add_argument("--src", type=Path)
    ap.add_argument("--package", type=Path)
    ap.add_argument("--pages", type=int, default=None)
    args = ap.parse_args()

    root = args.package or args.build
    stem = f"Q2D_Query-to-Data_Technical_Report_Draft_v{args.draft}"
    figures = (args.package or args.src) / "figures"

    print(f"verifying draft {args.draft} in {root}")
    digests = verify_figures(figures)
    verify_manuscript((args.src / "manuscript.md") if args.src
                      else (root / f"{stem}.md"), args.draft)
    verify_docx(root / f"{stem}.docx", args.draft, digests)
    verify_pdf(root / f"{stem}.pdf", args.pages)
    verify_package_prose(args.package, args.src, args.draft)
    if args.package:
        verify_checksums(args.package)

    print(f"\n{CHECKS - len(FAILURES)}/{CHECKS} checks passed")
    if FAILURES:
        print("FAILED:")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("build is deposit-ready")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
