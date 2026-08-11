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

import coverage as coverage_mode
import cross as cross_mode
import lint as lint_mode
import run as run_mode
from corpus import CorpusError
from schema import UnsupportedKeyword

DEFAULT_CORPUS = Path(__file__).resolve().parents[1] / "corpus"

USAGE = """usage: python3 conformance/harness <mode> [options]

modes:
  lint       [--corpus DIR]            corpus self-checks
  run        --impl PATH [--corpus DIR]  run a corpus against one runner
  coverage   [--corpus DIR]            claims with no citing vector
  cross      --a PATH --b PATH [--corpus DIR]  two runners over one corpus
"""


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] in ("-h", "--help"):
        print(USAGE, end="")
        return 0 if len(argv) > 1 else 2

    mode, args = argv[1], argv[2:]

    if mode not in ("lint", "run", "coverage", "cross"):
        print(f"harness: unknown mode {mode!r}\n\n{USAGE}", end="", file=sys.stderr)
        return 2

    options, problem = parse_options(mode, args)
    if problem:
        print(f"harness {mode}: {problem}\n\n{USAGE}", end="", file=sys.stderr)
        return 2

    try:
        if mode == "lint":
            return lint_mode.lint(options["corpus"])
        if mode == "coverage":
            return coverage_mode.coverage(options["corpus"])
        if mode == "cross":
            return cross_mode.cross(options["corpus"], options["a"], options["b"])
        return run_mode.run(options["corpus"], options["impl"])
    except (CorpusError, UnsupportedKeyword) as exc:
        print(f"harness {mode}: {exc}", file=sys.stderr)
        return 2


def parse_options(mode: str, args: list[str]) -> tuple[dict, str]:
    """Flags for a mode, or a message saying why they are wrong.

    An unrecognised flag is an error rather than something ignored: a typo in a
    CI invocation should not silently run something other than what was asked
    for.
    """
    allowed = {"lint": {"--corpus"}, "coverage": {"--corpus"},
               "run": {"--corpus", "--impl"},
               "cross": {"--corpus", "--a", "--b"}}[mode]
    options = {"corpus": DEFAULT_CORPUS, "impl": None, "a": None, "b": None}

    remaining = list(args)
    while remaining:
        flag = remaining.pop(0)
        if flag not in allowed:
            return {}, f"unexpected argument {flag!r}"
        if not remaining:
            return {}, f"{flag} needs a value"
        options[flag.lstrip("-")] = Path(remaining.pop(0))

    if mode == "run" and options["impl"] is None:
        return {}, "--impl is required; there is nothing to run a corpus against"
    if mode == "cross" and (options["a"] is None or options["b"] is None):
        return {}, "--a and --b are both required; cross compares two runners"

    return options, ""


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
