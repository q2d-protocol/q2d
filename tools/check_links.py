#!/usr/bin/env python3
"""Every relative link in a tracked Markdown file resolves to something.

    python3 tools/check_links.py

CLAUDE.md's self-review asks for this by hand. The failures this repository has
actually recorded -- an escalation amended in two documents of four, a rule
restated in three places and updated in one -- are all the same shape: a
reference nobody re-read. A broken link is the cheapest detectable member of
that family, so it is worth detecting cheaply.

Scope, deliberately narrow:

- **Relative links only.** External URLs need the network, and a check that
  needs the network is a check that fails for reasons unrelated to the change.
- **Anchors are not verified.** Heading anchors would need a Markdown parser
  and would fail on every stylistic rename. The conformance linter does verify
  section anchors where it matters -- inside a vector's `requirement`, where a
  citation pointing at nothing reads as traceability.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# [text](target) and [text]: target, minus images, which are the same shape.
INLINE_LINK_RE = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)")
REFERENCE_LINK_RE = re.compile(r"^\s*\[[^\]]+\]:\s*(\S+)", re.MULTILINE)

EXTERNAL_PREFIXES = ("http://", "https://", "mailto:", "tel:", "#")


def tracked_markdown() -> list[Path]:
    """Ask git, so gitignored trees are out of scope without a second list."""
    listing = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files", "*.md", "**/*.md"],
        capture_output=True, text=True, check=True).stdout.split()
    return [REPO_ROOT / name for name in sorted(set(listing))]


def broken_links(doc: Path) -> list[str]:
    text = doc.read_text(encoding="utf-8")
    targets = INLINE_LINK_RE.findall(text) + REFERENCE_LINK_RE.findall(text)

    broken = []
    for target in targets:
        if target.startswith(EXTERNAL_PREFIXES):
            continue
        path = target.split("#", 1)[0]
        if not path:  # a bare anchor into this document
            continue
        if not (doc.parent / path).exists():
            broken.append(target)
    return broken


def main() -> int:
    documents = tracked_markdown()
    failures = 0

    for doc in documents:
        broken = broken_links(doc)
        if broken:
            failures += len(broken)
            print(f"  FAIL  {doc.relative_to(REPO_ROOT)}")
            for target in broken:
                print(f"          {target} does not exist")

    print(f"\n{len(documents)} markdown files checked")
    if failures:
        print(f"FAILED: {failures} broken link(s)")
        return 1
    print("every relative link resolves")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
