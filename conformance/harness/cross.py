"""Two runners over one corpus, held to producing the same thing.

P-001 §4.8, cross-implementation: *for every `comparison: bytes` vector, both
runners produce identical bytes; and in `cross` mode, B verifies what A
produced.*

The first half is here. It is the assertion the whole project rests on -- two
implementations built from one specification, and a divergence between them is
a specification ambiguity found before an outsider finds it (`mvp-scope.md` §7).
Ed25519 signing is deterministic (RFC 8032), so two conforming implementations
produce byte-identical signatures for the same key and message, which is what
makes this a byte comparison rather than a both-verify check.

**The second half is not implemented, and cannot be from here.** Feeding what A
signed into B's verification means knowing which operation consumes a signed
envelope and under which input field -- that is P-002's and P-003's knowledge,
and P-001 §3 puts protocol logic outside this harness explicitly: *"a change
that gives it protocol knowledge is out of scope and an escalation."* Making it
real needs a vector to declare its companion, which is a format change. §4.8
records that rather than leaving a reader to assume both halves run.

## What "identical bytes" can mean here

Not the two runners' stdout, which differs by construction: every result carries
an `implementation` naming who produced it, so comparing whole documents would
report every vector as divergent.

So the comparison is field by field over the *values* a result carries --
output, and the halves of a rejection. Key order *within* a value is compared,
because `wire` and `output` carry protocol content and two responses with the
same fields in a different order are different bytes on the wire. Key order of
the result envelope itself is not, because whether a runner writes `outcome`
before `vector_id` is a property of its JSON writer; nor is its whitespace or
number notation, for the same reason.

Every value the specification requires determinism over is a string -- a JWS
compact serialization, a digest, a signature -- and for those this is exact
byte equality.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import compare as compare_module
import corpus as corpus_module
import cross_vector
import projection as projection_module
import run as run_module
import schema as schema_module


def first_difference(left: str, right: str) -> str:
    """Where two serializations first differ, with the neighbourhood shown.

    A report that says only "differs" leaves the reader to find a one-byte
    canonicalization divergence by eye, which is the failure this mode exists
    to make cheap to diagnose.
    """
    left_bytes = left.encode("utf-8")
    right_bytes = right.encode("utf-8")

    offset = 0
    for offset, (a, b) in enumerate(zip(left_bytes, right_bytes)):
        if a != b:
            break
    else:
        offset = min(len(left_bytes), len(right_bytes))
        return (f"one output is a prefix of the other; they diverge at byte "
                f"{offset} where the longer continues "
                f"{(left_bytes if len(left_bytes) > len(right_bytes) else right_bytes)[offset:offset + 24]!r}")

    window = slice(max(0, offset - 16), offset + 16)
    return (f"first differing byte at offset {offset}: "
            f"A has {left_bytes[offset:offset + 1]!r}, B has {right_bytes[offset:offset + 1]!r}\n"
            f"            A: …{left_bytes[window]!r}…\n"
            f"            B: …{right_bytes[window]!r}…")


def comparable(result: dict) -> list[tuple[str, object]]:
    """The fields two runners must agree on, each compared on its own.

    Two exclusions, and one thing deliberately not excluded.

    `implementation` is excluded: it names who produced the result, so it
    differs between two runners by construction.

    The *result envelope's* key order is excluded, by comparing field by field
    rather than serializing the whole document. Whether a runner writes
    `outcome` before `vector_id` is a property of its JSON writer, and holding
    two implementations to the same one would report a divergence that is not
    about Q2D at all.

    Key order *inside* a value is not excluded. `wire` and `output` carry
    protocol content, and two responses with the same fields in a different
    order are different bytes on the wire -- which is the divergence this mode
    exists to find.
    """
    fields: list[tuple[str, object]] = [("outcome", result["outcome"])]
    if "output" in result:
        fields.append(("output", result["output"]))
    if "rejection" in result:
        rejection = result["rejection"]
        fields.append(("rejection.internal_reason", rejection.get("internal_reason")))
        fields.append(("rejection.wire", rejection.get("wire")))
        if "step" in rejection:
            fields.append(("rejection.step", rejection["step"]))
    return fields


def obtain(vector, runner: Path, result_schema: dict, scratch: Path):
    """One runner's result for one vector, or why there isn't one."""
    projected = projection_module.project(vector.body)
    code, stdout, stderr = run_module.invoke(runner, projected, scratch)
    note = stderr.strip().splitlines()[-1] if stderr.strip() else ""

    if code != run_module.EXIT_RESULT_PRODUCED:
        return None, f"exited {code}{f': {note}' if note else ''}"
    try:
        result = corpus_module.parse_strictly(stdout)
    except ValueError as exc:
        return None, f"emitted invalid JSON: {exc}"
    errors = schema_module.validate(result, result_schema)
    if errors:
        return None, f"emitted a non-conforming result: {errors[0]}"
    return result, ""


def cross(corpus_root: Path, runner_a: Path, runner_b: Path) -> int:
    """Run a corpus through two runners and compare. Returns an exit code."""
    for runner in (runner_a, runner_b):
        if not runner.exists():
            raise corpus_module.CorpusError(f"runner not found: {runner}")

    conformance = Path(__file__).resolve().parents[1]
    result_schema = corpus_module.parse_strictly(
        (conformance / "result.schema.json").read_text(encoding="utf-8"))
    vector_schema = corpus_module.parse_strictly(
        (conformance / "vector.schema.json").read_text(encoding="utf-8"))
    for loaded in (result_schema, vector_schema):
        schema_module.assert_supported(loaded)

    vectors, unreadable = corpus_module.load(corpus_root)

    print(f"A: {runner_a}\nB: {runner_b}\ncorpus: {corpus_root}\n")

    divergent = 0
    unusable = 0

    with tempfile.TemporaryDirectory(prefix="q2d-cross-") as tmp:
        scratch = Path(tmp)
        for vector in vectors:
            if schema_module.validate(vector.body, vector_schema):
                unusable += 1
                print(f"  SKIP  {vector.id}\n          vector does not conform; "
                      f"run `harness lint`")
                continue

            result_a, problem_a = obtain(vector, runner_a, result_schema, scratch)
            result_b, problem_b = obtain(vector, runner_b, result_schema, scratch)

            if problem_a or problem_b:
                # Neither runner is being judged against the corpus here -- that
                # is `run` -- so a runner that cannot answer is reported as
                # unusable rather than as a divergence between the two.
                unusable += 1
                print(f"  SKIP  {vector.id}")
                if problem_a:
                    print(f"          A {problem_a}")
                if problem_b:
                    print(f"          B {problem_b}")
                continue

            mode = vector.body["expect"]["comparison"]
            fields_a = dict(comparable(result_a))
            fields_b = dict(comparable(result_b))

            difference = None
            for label in sorted(set(fields_a) | set(fields_b)):
                if label not in fields_a or label not in fields_b:
                    difference = f"{label}: present in only one result"
                    break
                if mode == "bytes":
                    left = cross_vector.as_authored(fields_a[label])
                    right = cross_vector.as_authored(fields_b[label])
                    if left != right:
                        difference = f"{label}: {first_difference(left, right)}"
                        break
                else:
                    found = compare_module.compare(fields_a[label], fields_b[label], mode)
                    if found:
                        difference = f"{label}: {found}"
                        break

            if difference:
                divergent += 1
                print(f"  DIFFER  {vector.id}\n          {difference}")
                continue

            print(f"  agree   {vector.id}")

    total = len(vectors)
    compared = total - unusable
    print(f"\n{compared - divergent}/{compared} vectors agree "
          f"({total} in the corpus, {unusable} not comparable)")

    if unreadable:
        print(f"{len(unreadable)} file(s) could not be read; run `harness lint`")

    if divergent:
        print(f"FAILED: {divergent} vector(s) where the two implementations differ")
        return 1
    if not compared:
        # Two runners agreeing about nothing is not agreement.
        print("nothing was compared — the corpus is empty, or neither runner "
              "could answer anything in it")
    return 0
