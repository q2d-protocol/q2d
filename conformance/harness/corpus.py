"""Loading a corpus, once, for every mode that needs one.

`lint`, `run`, `cross`, and `coverage` all begin by reading the same directory
of vectors. Reading it four ways would be four chances to disagree about what a
vector is, in the one component whose job is deciding whether two things agree.
"""

from __future__ import annotations

import json
from pathlib import Path


class CorpusError(Exception):
    """The corpus or its schema cannot be read, so nothing can be judged."""


def _reject_constant(token: str):
    """`json.loads` accepts NaN and Infinity; RFC 8259 does not."""
    raise ValueError(f"{token} is not valid JSON")


def _reject_duplicate_keys(pairs):
    """`json.loads` keeps the last of a repeated key and says nothing.

    A file whose meaning depends on which duplicate a parser keeps is not a
    shared contract, and core-model.md §2.1's envelope rules reject duplicates
    on the wire for the same reason.
    """
    seen = set()
    for key, _ in pairs:
        if key in seen:
            raise ValueError(f"duplicate object key {key!r}")
        seen.add(key)
    return dict(pairs)


def parse_strictly(text: str):
    """Parse as RFC 8259 JSON, not as what Python will tolerate.

    A vector the harness accepts and a Rust or Go runner rejects is a corpus
    that means two things, which is the one thing it may not be.
    """
    return json.loads(text, parse_constant=_reject_constant,
                      object_pairs_hook=_reject_duplicate_keys)


class Vector:
    """One authored vector, and where it came from."""

    __slots__ = ("path", "relative", "body")

    def __init__(self, path: Path, relative: Path, body):
        self.path = path
        self.relative = relative
        self.body = body

    @property
    def id(self) -> str:
        """The vector's id, or where it came from if it has none.

        A file that parses as JSON but is not an object -- a bare array, a
        string -- has no id to report, and reaching for one would crash the
        report rather than print it. Every mode has to be able to *name* a
        malformed vector in order to say it is malformed.
        """
        if isinstance(self.body, dict):
            identifier = self.body.get("id")
            if isinstance(identifier, str):
                return identifier
        return str(self.relative)

    @property
    def comparison(self) -> str:
        if not isinstance(self.body, dict):
            return ""
        return self.body.get("expect", {}).get("comparison", "")

    def __repr__(self) -> str:
        return f"Vector({self.id!r})"


def vector_files(corpus_root: Path) -> list[Path]:
    """Every vector file, in a stable order.

    Sorted, so two runs of the harness report in the same order. A report whose
    line order depends on the filesystem is one nobody can diff between runs.
    """
    if not corpus_root.is_dir():
        raise CorpusError(f"corpus directory not found: {corpus_root}")
    return sorted(p for p in corpus_root.rglob("*.json") if p.is_file())


def load(corpus_root: Path) -> tuple[list[Vector], list[tuple[Path, str]]]:
    """Every vector under `corpus_root`, and every file that would not parse.

    Unreadable files are returned rather than raised, so a mode can report them
    as failures alongside everything else. A corpus with one broken file is
    still a corpus worth running: reporting only the breakage would hide
    whatever else is wrong.
    """
    vectors: list[Vector] = []
    unreadable: list[tuple[Path, str]] = []

    for path in vector_files(corpus_root):
        try:
            body = parse_strictly(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            unreadable.append((path.relative_to(corpus_root), str(exc)))
            continue
        vectors.append(Vector(path, path.relative_to(corpus_root), body))

    return vectors, unreadable
