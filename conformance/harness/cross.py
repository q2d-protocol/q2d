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

    # A result for a different vector is not an answer to this one, and
    # `comparable()` deliberately drops `vector_id` -- so without this, two
    # runners that both returned the same canned result for some other vector
    # would be reported as agreeing across the whole corpus. `run` makes the
    # same check for the same reason; the mode that has *two* runners to be
    # wrong at once needs it more, not less.
    if result["vector_id"] != vector.body["id"]:
        return None, (f"answered {result['vector_id']!r}, not "
                      f"{vector.body['id']!r}")

    # `outcome: "error"` says the runner faulted internally -- it is the
    # contract's way of saying "no Q2D answer", not a Q2D answer of its own. A
    # vector cannot expect one (§4.6 admits `ok` and `rejected` only), and the
    # only field two errors share is the word `error`, so comparing them would
    # report agreement for a vector on which neither implementation produced
    # anything. It belongs with exit 1: no answer given.
    if result["outcome"] == "error":
        detail = result.get("detail")
        return None, f"faulted{f': {detail}' if detail else ''}"

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
    invalid = 0

    with tempfile.TemporaryDirectory(prefix="q2d-cross-") as tmp:
        scratch = Path(tmp)
        for vector in vectors:
            if schema_module.validate(vector.body, vector_schema):
                # Same class as a file that will not parse: a vector nobody was
                # asked about, so agreement across the corpus has not been
                # shown. Counted separately from an unusable *pair* -- this is
                # the corpus being wrong, not the runners.
                invalid += 1
                print(f"  INVALID  {vector.id}\n          vector does not conform; "
                      f"run `harness lint`")
                continue

            result_a, problem_a = obtain(vector, runner_a, result_schema, scratch)
            result_b, problem_b = obtain(vector, runner_b, result_schema, scratch)

            if problem_a and problem_b:
                # Neither runner is being judged against the corpus here -- that
                # is `run` -- so two runners that both cannot answer are
                # reported as unusable rather than as a divergence between
                # them. Neither claimed anything, so there is nothing they
                # disagree about.
                unusable += 1
                print(f"  SKIP  {vector.id}")
                print(f"          A {problem_a}")
                print(f"          B {problem_b}")
                continue

            if problem_a or problem_b:
                # One answered and one did not, which *is* the two of them
                # disagreeing: one implementation handles this vector and the
                # other does not. Treating it as unusable would let a `bytes`
                # vector that only one language implements pass this mode
                # silently, which is precisely the coverage gap the Stage 1
                # gate exists to close.
                divergent += 1
                side, problem = ("A", problem_a) if problem_a else ("B", problem_b)
                other = "B" if side == "A" else "A"
                print(f"  DIFFER  {vector.id}\n          {side} {problem}, "
                      f"while {other} produced a result")
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
    compared = total - unusable - invalid
    print(f"\n{compared - divergent}/{compared} vectors agree "
          f"({total} in the corpus, {unusable} not comparable, "
          f"{invalid} not conforming)")

    # Said on every run, including a clean one. §4.8 asks for two things and
    # this mode does one of them, so a bare "vectors agree" would read as the
    # whole requirement met. See the module docstring for why the other half
    # cannot be done from here.
    print("compared what each runner produced; did not put A's output to B for "
          "verification (P-001 §4.8, issue 19)")

    if unreadable:
        # A file that will not parse is a vector neither runner was asked
        # about, so the corpus this mode reported on is smaller than the corpus
        # on disk. Printing that beside a zero exit would make a partial run
        # look like a complete one, which is the shape of understatement that
        # matters most in a gate.
        print(f"{len(unreadable)} file(s) could not be read; run `harness lint`")
        for relative, problem in unreadable:
            print(f"  {relative}: {problem}")

    if divergent:
        print(f"FAILED: {divergent} vector(s) where the two implementations differ")
        return 1
    if unreadable or invalid:
        print(f"FAILED: {len(unreadable) + invalid} file(s) could not be put to "
              f"either runner, so agreement across the corpus has not been shown")
        return 1
    if not compared:
        # Two runners agreeing about nothing is not agreement, so this is a
        # failure and not a quiet zero. A gate that exits 0 having compared
        # nothing is the most expensive kind of green: it reports the property
        # holding on the days it was never tested.
        print("FAILED: nothing was compared — the corpus is empty, or neither "
              "runner could answer anything in it, so no agreement has been "
              "shown")
        return 1
    return 0
