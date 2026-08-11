"""Which claims no vector cites.

P-001 §4.8: every claim in `spec/claims.md` is cited by at least one vector, and
**uncited claims are reported, not silently absent**. A coverage tool that only
counts what exists cannot tell you what is missing, which is the only thing it
is for.

This is the instrument by which `claims.md`'s `Verified by: planned` entries
close. Today it reports thirteen uncovered, which is the correct Stage 0 answer
and not a failure -- the corpus is empty, and saying so precisely is more useful
than a number that could be read as progress.

**It reports; it does not gate.** Exiting non-zero while the corpus is
deliberately empty would put a permanently red check in CI, which trains
everyone to ignore red. The expected state is asserted in the test suite
instead, which is green while true and turns red when it stops being true.
P-016 issue 8 extends this into the traceability matrix, where the three claims
that will still have no passing test at the end of MVP are named in the same
table as the ten that pass.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import corpus as corpus_module
import lint as lint_module
import schema as schema_module
from lint import CLAIMS_PATH, CLASSES_PATH, SCHEMA_PATH, CorpusError

# Q2D-C-nn is a claim and needs covering. Q2D-NC-nn is a *non*-claim -- a thing
# the project states it does not claim -- so a vector may cite one, and nothing
# is missing when none does.
CLAIM_RE = re.compile(r"\bQ2D-C-[0-9]{2}\b")
NON_CLAIM_RE = re.compile(r"\bQ2D-NC-[0-9]{2}\b")
CLASS_RE = re.compile(r"\bCC-[0-9]{1,2}\b")


def numeric_order(identifier: str) -> tuple[str, int]:
    """Sort CC-2 before CC-12, which a string sort does not."""
    prefix, _, number = identifier.rpartition("-")
    return prefix, int(number)


def declared(path: Path, pattern: re.Pattern) -> list[str]:
    """Identifiers as `spec/` declares them, read rather than restated."""
    found = sorted(set(pattern.findall(path.read_text(encoding="utf-8"))),
                   key=numeric_order)
    if not found:
        raise CorpusError(f"no identifiers found in {path}; coverage would pass vacuously")
    return found


def citations(vectors) -> dict[str, list[str]]:
    """Every identifier cited, and which vectors cite it."""
    cited: dict[str, list[str]] = {}
    for vector in vectors:
        if not isinstance(vector.body, dict):
            continue
        for citation in vector.body.get("requirement", []) or []:
            if isinstance(citation, str):
                cited.setdefault(citation, []).append(vector.id)
    return cited


def report_block(title: str, identifiers: list[str], cited: dict[str, list[str]]) -> int:
    print(title)
    uncovered = 0
    for identifier in identifiers:
        citing = cited.get(identifier, [])
        if citing:
            print(f"  covered    {identifier}  ({len(citing)} vector"
                  f"{'s' if len(citing) > 1 else ''})")
        else:
            uncovered += 1
            print(f"  UNCOVERED  {identifier}")
    return uncovered


def coverage(corpus_root: Path) -> int:
    """Report claim coverage over a corpus. Returns a process exit code."""
    claims = declared(CLAIMS_PATH, CLAIM_RE)
    non_claims = declared(CLAIMS_PATH, NON_CLAIM_RE)
    classes = declared(CLASSES_PATH, CLASS_RE)

    vectors, unreadable = corpus_module.load(corpus_root)

    # Only a vector the corpus accepts may cover a claim, and "accepts" means
    # what `lint` means by it -- not merely schema-valid. A vector that is
    # misplaced, cites a section that does not exist, or sits in `ordering/`
    # without stating a step is one the corpus rejects; counting its citation
    # would report a claim as covered by evidence the corpus itself refuses.
    # claims.md's traceability rule is about checks that can actually run.
    vector_schema = corpus_module.parse_strictly(
        SCHEMA_PATH.read_text(encoding="utf-8"))
    schema_module.assert_supported(vector_schema)
    claim_ids, class_ids = lint_module.known_identifiers()
    sections = lint_module.citable_sections()

    # Duplicated identifiers are a property of the corpus rather than of a
    # vector, so they are checked here rather than in vector_errors -- and they
    # have to be checked, because lint rejects a corpus carrying them and a
    # claim covered only by a vector lint rejects is not covered.
    seen = Counter(v.id for v in vectors)

    countable = []
    rejected = []
    for vector in vectors:
        errors = lint_module.vector_errors(
            vector.body, vector.path, corpus_root, vector_schema,
            claim_ids, class_ids, sections)
        if seen[vector.id] > 1:
            errors = errors or ["duplicate identifier"]
        (rejected if errors else countable).append(vector)

    cited = citations(countable)

    print(f"coverage over {corpus_root}\n")

    uncovered = report_block("claims", claims, cited)
    print()
    report_block("conformance classes", classes, cited)

    referenced_non_claims = [n for n in non_claims if n in cited]
    if referenced_non_claims:
        # Not a coverage requirement: a non-claim is something the project
        # states it does *not* claim, so nothing is missing when no vector
        # cites one. Listed because a vector that does cite one -- an
        # adversarial vector naming the channel it exercises -- is worth
        # seeing.
        print(f"\nnon-claims cited by a vector: {', '.join(referenced_non_claims)}")

    print(f"\n{len(claims) - uncovered}/{len(claims)} claims covered by at least one vector")

    uncounted = len(unreadable) + len(rejected)
    if uncounted:
        # A citation the harness cannot read, or one belonging to a vector that
        # cannot run, is not evidence of anything. Each is named: §4.8 asks for
        # missing evidence to be reported rather than silently absent, and a
        # bare total is the silent version of that.
        print(f"\n{uncounted} file(s) were not counted; run `harness lint`")
        for relative, problem in unreadable:
            print(f"  could not be read  {relative}: {problem}")
        for vector in rejected:
            print(f"  corpus rejects it  {vector.id}")

    if uncovered == len(claims):
        print("no claim is covered — the corpus is empty, or cites nothing")

    # Reports rather than gates: see the module docstring.
    return 0
