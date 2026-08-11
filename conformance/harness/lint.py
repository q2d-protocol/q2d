"""Corpus self-checks: every vector is well formed and cites something real.

Lint is the corpus's own fail-closed path. A vector that cannot be validated is
rejected, not passed through with a warning.

This module carries the checks the vector schema cannot express by itself --
agreement between a vector's id, its section, and where it sits on disk, and
whether its citations resolve to a claim, a class, or a specification file that
exists. A citation that points at nothing is worse than no citation: it reads as
traceability in a table nobody re-derives.

P-001 issue 5 owns the remaining `harness lint` behaviour in P-001 §8.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import schema as schema_module

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO_ROOT / "conformance" / "vector.schema.json"
CLAIMS_PATH = REPO_ROOT / "spec" / "claims.md"
CLASSES_PATH = REPO_ROOT / "spec" / "conformance-classes.md"

# Citations resolve against both, because a vector may exercise something the
# threat model names rather than the specification.
CITABLE_DIRS = ("spec", "threat-model")

CLAIM_RE = re.compile(r"\bQ2D-(?:C|NC)-[0-9]{2}\b")
CLASS_RE = re.compile(r"\bCC-[0-9]{1,2}\b")
SPEC_CITATION_RE = re.compile(r"^([a-z0-9-]+\.md)#(.+)$")
# A numbered heading at any depth: '## 4. Processing order', '#### 2.4.1 The...'
HEADING_RE = re.compile(r"^#{1,6}\s+([0-9]+(?:\.[0-9]+)*)\b", re.MULTILINE)


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


def load_schema() -> dict:
    try:
        loaded = parse_strictly(SCHEMA_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CorpusError(f"vector schema not found at {SCHEMA_PATH}") from exc
    except ValueError as exc:  # JSONDecodeError is a ValueError
        raise CorpusError(f"vector schema is not valid JSON: {exc}") from exc
    # Fail before judging anything, rather than silently under-enforcing.
    schema_module.assert_supported(loaded)
    return loaded


def known_identifiers() -> tuple[set[str], set[str]]:
    """Claim and class identifiers, read from spec/ rather than restated here."""
    claims = set(CLAIM_RE.findall(CLAIMS_PATH.read_text(encoding="utf-8")))
    classes = set(CLASS_RE.findall(CLASSES_PATH.read_text(encoding="utf-8")))
    if not claims or not classes:
        raise CorpusError("no identifiers found in spec/; the citation check would pass vacuously")
    return claims, classes


def citable_sections() -> dict[str, set[str]]:
    """Numbered headings per citable document, read rather than restated."""
    sections: dict[str, set[str]] = {}
    for directory in CITABLE_DIRS:
        for path in sorted((REPO_ROOT / directory).glob("*.md")):
            sections[path.name] = set(HEADING_RE.findall(path.read_text(encoding="utf-8")))
    return sections


def citation_errors(vector: dict, claims: set[str], classes: set[str],
                    sections: dict[str, set[str]]) -> list[str]:
    errors = []
    for citation in vector.get("requirement", []):
        if not isinstance(citation, str):
            continue  # the schema already reported this
        if CLAIM_RE.fullmatch(citation):
            if citation not in claims:
                errors.append(f"requirement: {citation} is not a claim in spec/claims.md")
        elif CLASS_RE.fullmatch(citation):
            if citation not in classes:
                errors.append(f"requirement: {citation} is not a class in spec/conformance-classes.md")
        else:
            match = SPEC_CITATION_RE.match(citation)
            if not match:
                continue  # the schema's pattern already reported this
            document, section = match.groups()
            if document not in sections:
                errors.append(
                    f"requirement: {citation} cites {document}, which is not a document in "
                    + " or ".join(f"{d}/" for d in CITABLE_DIRS))
            elif section not in sections[document]:
                # A citation to a section that does not exist is worse than no
                # citation: it reads as traceability to anyone who does not
                # re-derive it.
                errors.append(f"requirement: {citation} cites a section {document} does not have")
    return errors


def placement_errors(vector: dict, path: Path, corpus_root: Path) -> list[str]:
    """The id, the section, and the directory must all say the same thing."""
    errors = []
    section = vector.get("section")
    vector_id = vector.get("id")

    if isinstance(vector_id, str) and isinstance(section, str):
        if vector_id.split("/", 1)[0] != section:
            errors.append(f"id: {vector_id!r} does not start with its section {section!r}")

    if isinstance(section, str):
        relative = path.relative_to(corpus_root).parts
        if len(relative) < 2 or relative[0] != section:
            errors.append(f"section: {section!r} but the file sits at {'/'.join(relative)}")

    return errors


def lint(corpus_root: Path) -> int:
    """Validate every vector under `corpus_root`. Returns a process exit code."""
    if not corpus_root.is_dir():
        raise CorpusError(f"corpus directory not found: {corpus_root}")

    vector_schema = load_schema()
    claims, classes = known_identifiers()
    sections = citable_sections()

    print(f"linting {corpus_root} against {SCHEMA_PATH.name}\n")

    failures = 0
    seen: dict[str, Path] = {}
    files = sorted(p for p in corpus_root.rglob("*.json") if p.is_file())

    for path in files:
        label = path.relative_to(corpus_root)
        try:
            vector = parse_strictly(path.read_text(encoding="utf-8"))
        except ValueError as exc:  # JSONDecodeError is a ValueError
            print(f"  FAIL  {label}\n          not valid JSON: {exc}")
            failures += 1
            continue

        errors = schema_module.validate(vector, vector_schema)
        if isinstance(vector, dict):
            errors += placement_errors(vector, path, corpus_root)
            errors += citation_errors(vector, claims, classes, sections)

            vector_id = vector.get("id")
            if isinstance(vector_id, str):
                if vector_id in seen:
                    errors.append(f"id: {vector_id!r} already used by {seen[vector_id]}")
                else:
                    seen[vector_id] = label

        if errors:
            failures += 1
            print(f"  FAIL  {label}")
            for error in errors:
                print(f"          {error}")
        else:
            print(f"  ok    {label}")

    print(f"\n{len(files) - failures}/{len(files)} vectors valid")
    if failures:
        print(f"FAILED: {failures} vector(s) rejected")
        return 1
    if not files:
        # Vacuously clean, and worth saying: an empty corpus lints green and
        # proves nothing. `harness coverage` is what reports the emptiness.
        print("corpus is empty")
    return 0
