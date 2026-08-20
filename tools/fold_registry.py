#!/usr/bin/env python3
"""Derive the corpus's `registry/` section from the registry manifest.

    python3 tools/fold_registry.py            # write conformance/corpus/registry/
    python3 tools/fold_registry.py --check    # fail if what is committed differs

[P-001](../docs/prds/P-001-conformance-corpus.md) §5 marks `registry/` as
**folded in from** [`registry/manifest.json`](../registry/manifest.json), and
issue 11's acceptance is that the registry vectors *"run under the harness with
unchanged results"*.

**Generated rather than transcribed, because the manifest outranks the corpus.**
[CLAUDE.md](../CLAUDE.md)'s hierarchy puts `registry/manifest.json` above the
corpus: it is where a predicate's domain, capacity, and validation live. Copying
fourteen vectors by hand would make a second place where they live, and the two
would agree exactly until the first time somebody edited one. Here the manifest
is read every time, and `--check` in CI turns a divergence into a failing build
rather than a corpus quietly asserting last month's registry.

## What the translation does, and what it cannot carry

A manifest vector and a corpus vector answer different questions. The manifest's
asks *"does a reference evaluation of this predicate produce this?"*; the
corpus's asks *"does this implementation?"*. The fields map directly, with two
exceptions worth stating rather than burying:

- **`before_private_access` has no corpus field.** The manifest says a rejection
  happened before private input was read; the corpus format says a rejection
  happened at a numbered step of [`core-model.md`](../spec/core-model.md) §4,
  which is a stronger statement where the step is determined and no statement at
  all where it is not. `public_context_schema_violation` is step 11 — *"public
  context validated against the entry's input schema"* — and is stated as such.
  `constraint_violation_minimum_slot_duration` is **step 11a** — the entry's
  constraints that its input schema cannot express, which a minimum slot
  duration is. That was undetermined until it was raised as an escalation and
  §4 gained the step; the vector stated no step meanwhile, which is what §4.8
  makes a step-less vector mean, rather than this generator picking one.
- **The evaluation itself is not carried.** `registry/validate.py` holds a
  deliberately naive reference evaluation to pin the vectors' meaning. Nothing
  of it appears in the corpus: a vector states what a conforming implementation
  produces, and how the reference produced it is not part of that.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MANIFEST = REPO / "registry" / "manifest.json"
SECTION = REPO / "conformance" / "corpus" / "registry"

# core-model.md §4's two public-context checks, which are two steps because they
# are two mechanisms: step 11 runs the entry's input schema, and step 11a checks
# the constraints that schema cannot express.
STEP_FOR_REASON = {
    "public_context_schema_violation": 11,
    "constraint_violation_minimum_slot_duration": "11a",
}

# What each kind of vector demonstrates. Answers exercise the released result
# and its debit; rejections exercise the denial the requester actually sees.
# CC-2 on both: a responder validating public context against the registry's
# schema, debiting once, and failing closed is doing CC-2's work whether the
# vector ends in an answer or a denial.
# Q2D-C-09 was here until 2026-08-19. It is **not attempted in this release**
# (claims.md), so these vectors no longer cite it and no longer assert a debit:
# a vector citing a claim nothing implements reports coverage that does not
# exist, which is the overstatement claims.md's traceability rule forbids.
#
# The manifest keeps its capacity values. Removing them would change what a
# registry entry *is* -- terminology.md §3 makes capacity part of the
# definition -- which is a registry-semantics change and a separate decision
# from deferring the claim.
REQUIREMENTS_ANSWER = ["Q2D-C-03", "CC-2", "core-model.md#4"]
REQUIREMENTS_REJECTION = ["Q2D-C-08", "CC-2", "core-model.md#4"]


def short_name(predicate_id: str) -> str:
    return predicate_id.rstrip("/").rsplit("/", 1)[-1]


def translate(predicate: dict, vector: dict) -> dict:
    """One manifest vector as one corpus vector."""
    name = short_name(predicate["id"])
    expect = vector["expect"]
    rejecting = expect["outcome"] == "reject"

    body = {
        "id": f"registry/{name}/{vector['name']}",
        "section": "registry",
        "requirement": (REQUIREMENTS_REJECTION if rejecting
                        else REQUIREMENTS_ANSWER),
        "description": describe(predicate, vector),
        "operation": "evaluate_predicate",
        "input": {
            "predicate": {"id": predicate["id"], "version": predicate["version"]},
            "public_context": vector["public_context"],
            "private_input": vector["private_input"],
        },
    }

    if rejecting:
        rejection = {
            "internal_reason": expect["internal_reason"],
            "wire": expect["wire"],
        }
        step = STEP_FOR_REASON.get(expect["internal_reason"])
        if step is not None:
            rejection["step"] = step
        body["expect"] = {
            "outcome": "rejected",
            "rejection": rejection,
            # `bytes`, and it is not currently checkable. §4.4 says `bytes`
            # "where the spec requires determinism", and a normalized denial is
            # the clearest case in the protocol: Q2D-C-08 holds only when the
            # external envelope and its size are *identical* for every internal
            # cause in the class, which is a statement about serialized bytes.
            # Declaring `semantic` would say the specification requires no
            # determinism here, which is false, and §4.4 warns that this is
            # exactly how a determinism requirement gets quietly dropped.
            #
            # `harness cross` cannot make that comparison, because a runner
            # reports `wire` as a parsed object and the bytes are gone before
            # the harness sees them -- so it reports these five UNCHECKABLE and
            # fails. That is the intended outcome: P-001 §10 asks whether the
            # result format should carry the serialization, and until it is
            # answered the gap belongs in every cross run rather than hidden
            # behind a mode declaration that understates the requirement.
            "comparison": "bytes",
        }
    else:
        body["expect"] = {
            "outcome": "ok",
            # The manifest's own field names, kept. Renaming them here would
            # make the corpus and the registry describe one value two ways,
            # and the registry is the one that governs.
            #
            # `semantic` below, unlike the rejections: an evaluation result is
            # not a signed artefact and no part of the specification requires
            # determinism over how it is serialized. The values still have to
            # match exactly -- `semantic` is parse-then-deep-equal with no
            # coercion.
            # The debit is **not** asserted since 2026-08-19: Q2D-C-09 is not
            # attempted, so nothing computes one and a vector expecting a value
            # no implementation produces would fail for the wrong reason. The
            # manifest still carries it; the corpus stops checking it.
            "output": {
                "result": expect["result"],
            },
            "comparison": "semantic",
        }

    return body


def describe(predicate: dict, vector: dict) -> str:
    expect = vector["expect"]
    if expect["outcome"] == "reject":
        detail = f"rejects with {expect['internal_reason']}"
        if expect.get("before_private_access"):
            if expect["internal_reason"] in STEP_FOR_REASON:
                # The step says it and is checked. Saying it again in prose is
                # a restatement, not a second claim.
                detail += ", at a step before private input is read"
            else:
                # Every rejection reason the manifest carries now has a step,
                # so this branch is unreachable today. It stays because the next
                # predicate may add a reason before §4 has a step for it, and
                # the right behaviour then is what it was: say what the manifest
                # asserts, and do not let the corpus assert an ordering nothing
                # checks.
                detail += (". The manifest also records that this rejection "
                           "precedes private access; this vector does not "
                           "assert it, because no §4 step is determined for "
                           "this reason")
    else:
        detail = f"answers {json.dumps(expect['result'])}"
    return (f"{predicate['title']} ({short_name(predicate['id'])}): "
            f"{vector['name']} — {detail}. Folded from registry/manifest.json "
            f"by tools/fold_registry.py; edit the manifest, not this file.")


def generate() -> dict[Path, str]:
    """Every vector file this fold produces, as path → contents."""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    files: dict[Path, str] = {}

    for predicate in manifest["predicates"]:
        name = short_name(predicate["id"])
        for vector in predicate["test_vectors"]:
            body = translate(predicate, vector)
            path = SECTION / name / f"{vector['name']}.json"
            files[path] = json.dumps(body, indent=2, ensure_ascii=False) + "\n"

    if not files:
        raise SystemExit("fold_registry: the manifest declared no test vectors; "
                         "refusing to write an empty section over a real one")
    return files


def main(argv: list[str]) -> int:
    checking = "--check" in argv[1:]
    files = generate()

    committed = {path for path in SECTION.rglob("*.json")} if SECTION.is_dir() else set()
    stale = sorted(committed - set(files))

    differences = []
    for path, contents in sorted(files.items()):
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current == contents:
            continue
        differences.append(path)
        if not checking:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(contents, encoding="utf-8")

    if checking:
        for path in differences:
            print(f"differs from the manifest: {path.relative_to(REPO)}")
        for path in stale:
            # A vector the manifest no longer declares. Left in place it would
            # keep asserting a predicate the registry has dropped.
            print(f"not declared by the manifest: {path.relative_to(REPO)}")
        if differences or stale:
            print(f"\nFAILED: {len(differences) + len(stale)} file(s) out of "
                  f"step with registry/manifest.json — run "
                  f"`python3 tools/fold_registry.py`")
            return 1
        print(f"{len(files)} vector(s) match registry/manifest.json")
        return 0

    for path in stale:
        path.unlink()
        print(f"removed (no longer in the manifest): {path.relative_to(REPO)}")
    print(f"wrote {len(differences)} of {len(files)} vector(s) to "
          f"{SECTION.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
