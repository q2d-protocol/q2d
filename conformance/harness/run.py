"""Executing a corpus against one runner, and judging what comes back.

P-001 §4.8, per vector: outcome matches; output matches under the declared
comparison mode; and for rejections, the internal reason, the wire response,
and the step all match -- where "the step matches" means what §4.8 says it
means, which is that a vector *stating* a step is held to it. A vector that
states none asserts nothing about where the rejection happened, so an
implementation rejecting at the wrong step passes that vector; the vectors that
care about ordering say so, and `ordering/` is the section of them.

Three properties of how this is done, each of which is a rule somewhere:

- **The runner sees the projection, never the vector** (§4.2). The projection is
  written to a scratch file and that path is what the runner is given; the
  authored corpus path is never passed to a subprocess.
- **The runner reports; the harness judges** (§9.4). Nothing here asks a runner
  whether it passed. It is asked what happened, and compared against what the
  vector says should happen.
- **A malformed result is a runner failure, not a vector failure.** They are
  reported differently on purpose: one means the implementation is wrong about
  Q2D, the other means it is wrong about the contract, and conflating them
  sends whoever is debugging to the wrong file.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

import compare as compare_module
import corpus as corpus_module
import projection as projection_module
import schema as schema_module

# P-001 §4.1's exit statuses, from the runner's side.
EXIT_RESULT_PRODUCED = 0
EXIT_CANNOT_PROCESS = 1

# How long one vector may take. A runner that hangs must not hang the suite:
# the harness has to be able to report "this one never answered" rather than
# stopping at it.
TIMEOUT_SECONDS = 30


class Outcome:
    """What the harness concluded about one vector."""

    __slots__ = ("vector", "passed", "reason", "runner_failed")

    def __init__(self, vector, passed: bool, reason: str = "", runner_failed: bool = False):
        self.vector = vector
        self.passed = passed
        self.reason = reason
        self.runner_failed = runner_failed


def invoke(runner: Path, projected: dict, scratch: Path) -> tuple[int, str, str]:
    """Write the projection, run the runner over it, return what it said."""
    vector_file = scratch / "vector.json"
    # sort_keys for a byte-identical projection between runs: a runner that
    # digests its input must see no difference the corpus did not intend.
    vector_file.write_text(json.dumps(projected, sort_keys=True), encoding="utf-8")

    try:
        completed = subprocess.run(
            [str(runner), str(vector_file)],
            capture_output=True, timeout=TIMEOUT_SECONDS,
            # Explicit, because `text=True` alone decodes using the process
            # locale: the same runner emitting the same UTF-8 JSON would then
            # be judged differently on a machine configured differently, and a
            # conformance result that depends on where it ran is not one.
            text=True, encoding="utf-8", errors="strict")
    except subprocess.TimeoutExpired:
        return -1, "", f"no result within {TIMEOUT_SECONDS}s"
    except UnicodeDecodeError as exc:
        return -1, "", f"output is not UTF-8: {exc}"
    except OSError as exc:
        return -1, "", f"could not execute the runner: {exc}"

    return completed.returncode, completed.stdout, completed.stderr


def judge(vector, result: dict) -> tuple[bool, str]:
    """Compare a well-formed result against what the vector expects."""
    expect = vector.body["expect"]
    expected_outcome = expect["outcome"]
    actual_outcome = result["outcome"]

    if actual_outcome != expected_outcome:
        detail = result.get("detail")
        suffix = f" ({detail})" if actual_outcome == "error" and detail else ""
        return False, f"expected outcome {expected_outcome!r}, got {actual_outcome!r}{suffix}"

    if expected_outcome == "ok":
        difference = compare_module.compare(
            expect["output"], result["output"], expect["comparison"])
        if difference:
            return False, f"output differs under {expect['comparison']}: {difference}"
        return True, ""

    # A rejection is checked on both halves and on where it happened. Checking
    # only the wire response would pass an implementation that returned the
    # right denial for the wrong reason, which is the failure the internal /
    # external split exists to make visible.
    expected_rejection = expect["rejection"]
    actual_rejection = result["rejection"]

    if actual_rejection["internal_reason"] != expected_rejection["internal_reason"]:
        return False, (f"internal reason: expected "
                       f"{expected_rejection['internal_reason']!r}, got "
                       f"{actual_rejection['internal_reason']!r}")

    difference = compare_module.compare(
        expected_rejection["wire"], actual_rejection["wire"], expect["comparison"])
    if difference:
        return False, f"wire response differs: {difference}"

    # Where a vector states a step, it must match: a step that has silently
    # moved is the ordering failure `ordering/` exists to catch, and it is
    # invisible in the wire response. A vector that states none asserts nothing
    # about where the rejection happened, and a runner may still report one --
    # P-001 §4.6 makes the field optional, and §4.8 now says what that means.
    expected_step = expected_rejection.get("step")
    if expected_step is not None:
        actual_step = actual_rejection.get("step")
        if actual_step != expected_step:
            return False, f"rejected at step {actual_step!r}, expected {expected_step!r}"

    return True, ""


def run_vector(vector, runner: Path, result_schema: dict, vector_schema: dict,
               scratch: Path) -> Outcome:
    # A vector that does not conform cannot be judged, and reaching into it
    # anyway would abort the suite on the first malformed file -- hiding every
    # result after it. Fail-closed applies to the corpus as much as to a
    # runner, and `harness lint` is where the detail lives.
    errors = schema_module.validate(vector.body, vector_schema)
    if errors:
        return Outcome(vector, False,
                       f"vector does not conform to the schema: {errors[0]} "
                       f"(run `harness lint` for the whole picture)")

    try:
        projected = projection_module.project(vector.body)
    except KeyError as exc:
        return Outcome(vector, False, f"vector cannot be projected: missing {exc}")

    code, stdout, stderr = invoke(runner, projected, scratch)
    note = stderr.strip().splitlines()[-1] if stderr.strip() else ""

    if code != EXIT_RESULT_PRODUCED:
        reason = {
            EXIT_CANNOT_PROCESS: "runner could not process the vector",
        }.get(code, f"runner exited {code}")
        return Outcome(vector, False, f"{reason}{f': {note}' if note else ''}",
                       runner_failed=True)

    try:
        result = corpus_module.parse_strictly(stdout)
    except ValueError as exc:
        return Outcome(vector, False, f"result is not valid JSON: {exc}", runner_failed=True)

    errors = schema_module.validate(result, result_schema)
    if errors:
        return Outcome(vector, False, f"result does not conform: {errors[0]}",
                       runner_failed=True)

    if result["vector_id"] != vector.body["id"]:
        # A runner answering a different question would otherwise be scored on
        # this vector's expectation.
        return Outcome(vector, False,
                       f"result is for {result['vector_id']!r}, not {vector.body['id']!r}",
                       runner_failed=True)

    passed, reason = judge(vector, result)
    return Outcome(vector, passed, reason)


def run(corpus_root: Path, runner: Path) -> int:
    """Run every vector against one runner. Returns a process exit code."""
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

    print(f"running {corpus_root} against {runner}\n")

    failures = 0
    runner_failures = 0

    for relative, problem in unreadable:
        failures += 1
        print(f"  FAIL  {relative}\n          not valid JSON: {problem}")

    with tempfile.TemporaryDirectory(prefix="q2d-conform-") as tmp:
        scratch = Path(tmp)
        for vector in vectors:
            outcome = run_vector(vector, runner, result_schema, vector_schema, scratch)
            if outcome.passed:
                print(f"  ok    {vector.id}")
                continue
            failures += 1
            runner_failures += bool(outcome.runner_failed)
            print(f"  FAIL  {vector.id}\n          {outcome.reason}")

    total = len(vectors) + len(unreadable)
    print(f"\n{total - failures}/{total} vectors passed")

    if runner_failures:
        # Named separately because it sends the reader to a different file: a
        # runner that did not produce a judgeable result is wrong about the
        # contract, not about Q2D.
        print(f"{runner_failures} of those failed before comparison — the runner "
              f"did not produce a result the harness could judge")

    if failures:
        print(f"FAILED: {failures} vector(s)")
        return 1
    if not total:
        print("corpus is empty — nothing was run, and nothing is proven")
    return 0
