"""What a runner is allowed to see.

P-001 §4.2: the harness strips `expect` before writing the file the runner
reads, and implementations are never given a path to the authored corpus. An
implementation that can read the expected output can pass by reproducing it,
and the corpus is only evidence if the implementation is answering the question
rather than copying the answer.

**The projection is built from an allowlist, not by deleting a key.** Deleting
`expect` leaves the rule true only for the fields someone thought of: a later
`expect_bytes`, `expected`, or `notes_for_the_runner` would sail through a
delete and be caught by an allowlist. P-001 §6 fixes the shape --
`VectorInput = { id, operation, input }` -- so the allowlist is that shape and
nothing else.

`input` is copied whole and untouched. A key called `expect` *inside* `input`
is protocol data the operation needs, not an expectation, and a projection that
reached inside to remove it would corrupt the vector it was protecting.

**Escalate-if-changed (P-001 §9.1).** Letting an implementation see the
expectation makes the corpus unfalsifiable.
"""

from __future__ import annotations

# The field set is P-001 §6's `VectorInput`. The *order* is not: §6 fixes what
# a runner receives, not how it is serialized. Fixing it here is a harness
# decision with its own reason -- two runs must write byte-identical projection
# files, so a runner that digests its input sees no difference the corpus did
# not intend -- and P-001 §4.2 records it rather than leaving it in this tuple.
PROJECTED_FIELDS = ("id", "operation", "input")


def project(vector: dict) -> dict:
    """The input-only projection of an authored vector.

    Raises KeyError if the vector lacks a projected field, rather than emitting
    a partial projection: a runner handed a vector with no `operation` cannot
    report a result, and the harness would be judging its own omission.
    """
    return {field: vector[field] for field in PROJECTED_FIELDS}
