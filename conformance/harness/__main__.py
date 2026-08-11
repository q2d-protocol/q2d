"""The Q2D conformance harness.

    python3 conformance/harness lint [--corpus DIR]

The harness imports neither implementation and implements no Q2D behaviour: it
reads JSON, will invoke a subprocess, and compares (P-001 §3, §4.7). It is
Python so that a canonicalization or digest error present in both
implementations cannot cancel out inside the thing judging them.

Modes are built one issue at a time. An unbuilt mode exits non-zero rather than
reporting nothing to see -- P-001 §7: a harness that cannot fail is not a
harness, and one that silently succeeds is worse.
"""

from __future__ import annotations

import sys
from pathlib import Path

import lint as lint_mode
from lint import CorpusError
from schema import UnsupportedKeyword

DEFAULT_CORPUS = Path(__file__).resolve().parents[1] / "corpus"

PENDING = {
    "run": ("P-001 issue 4", "executes a corpus against one runner"),
    "cross": ("P-001 issue 9", "A produces, B verifies"),
    "coverage": ("P-001 issue 6", "claims with no citing vector"),
}

USAGE = """usage: python3 conformance/harness <mode> [options]

modes:
  lint       [--corpus DIR]   corpus self-checks (P-001 issue 5 completes these)
  run        [--impl PATH]    not built yet -- P-001 issue 4
  cross      [--a P --b P]    not built yet -- P-001 issue 9
  coverage                    not built yet -- P-001 issue 6
"""


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] in ("-h", "--help"):
        print(USAGE, end="")
        return 0 if len(argv) > 1 else 2

    mode, args = argv[1], argv[2:]

    if mode in PENDING:
        issue, summary = PENDING[mode]
        print(f"harness {mode}: not built yet -- {issue} ({summary})", file=sys.stderr)
        return 2

    if mode != "lint":
        print(f"harness: unknown mode {mode!r}\n\n{USAGE}", end="", file=sys.stderr)
        return 2

    corpus = DEFAULT_CORPUS
    if args:
        if args[0] != "--corpus" or len(args) != 2:
            print(f"harness lint: unexpected arguments {' '.join(args)!r}\n\n{USAGE}",
                  end="", file=sys.stderr)
            return 2
        corpus = Path(args[1])

    try:
        return lint_mode.lint(corpus)
    except (CorpusError, UnsupportedKeyword) as exc:
        print(f"harness lint: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
