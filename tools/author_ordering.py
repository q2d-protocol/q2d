#!/usr/bin/env python3
"""Author the corpus's `ordering/` section from the specification text.

    python3 tools/author_ordering.py            # write conformance/corpus/ordering/
    python3 tools/author_ordering.py --check    # fail if what is committed differs

[P-001](../docs/prds/P-001-conformance-corpus.md) §5 gives `ordering/` as *"one
vector per rejection step, 1–15 and the lettered steps among them, 5a, 9a and
11a"*, and issue 14 authors it.
[P-010](../docs/prds/P-010-responder-pipeline.md) §4.2 gives the reason: the
assertion is that a request malformed in a given way rejects at **exactly** the
expected step, *"which catches a check that has silently moved earlier or
later"*.

## Every vector uses `process_query`, and that is the point

A `verify_query` vector can show that a bad signature is refused. It cannot show
that the signature was checked **before** the registry was consulted, because it
never consults one. Ordering is a property of the pipeline, so `ordering/` runs
the pipeline — one operation for the whole section, so that no vector's step
number is an artefact of which operation it happened to use.

Each request is wrong in **exactly one way**, and the vector asserts the step
that catches it. A request wrong in two ways establishes nothing: it would reject
at the earlier of them whatever the implementation did with the later.

## Where this section stops, and why it is a hard line

**A vector asserting rejection at step N must *pass* steps 1 to N-1.** That is
the constraint that bounds this section, and it is stricter than it first looks:
it is not enough that step N's own defect be expressible, because a request that
cannot get past an earlier step is a request wrong in two ways, and a fail-closed
implementation will correctly reject it at the earlier one. Such a vector fails
*conforming* implementations.

**Step 7 is where that line falls.** Delegation verification needs a profile and
evidence, and [P-014](../docs/prds/P-014-identity-pairing.md) has not defined a
fixture format for either. Nothing at or after step 7 can be authored, because
nothing can be shown to get past it — not step 8, whose defect is otherwise
perfectly expressible, and not steps 10 to 13, whose registry is in hand.

So this file covers steps **1, 3, 4, 5, 5a and 6**, and the section is completed
by [P-010](../docs/prds/P-010-responder-pipeline.md) issue 11 once the fixtures
exist: a delegation profile (P-014), replay and rate-limit state
([P-004](../docs/prds/P-004-replay-idempotency.md)), a rule set
([P-007](../docs/prds/P-007-policy-engine.md)), budget state
([P-008](../docs/prds/P-008-capacity-accounting.md)).

**Step 2 gets no vector, and that is a statement rather than a gap.** §4 makes it
*optional* and *"never a security decision"*, so there is no rejection to assert:
a responder that sheds there and one that does not are both conforming, and a
vector asserting either would make one of them fail.

[P-010](../docs/prds/P-010-responder-pipeline.md) §6 owns this section and its
issue 11 completes it. This file authors the steps whose input needs no fixture
beyond the registry, so the ordering they establish exists before Stage 4 rather
than after it — which is the order P-001 §7's gate wants.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import author_vectors as av  # noqa: E402
from author_message import QUERY, ROUTING, REQUESTER, IMPOSTOR, seed_of  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
SECTION = REPO / "conformance" / "corpus" / "ordering"

UNREGISTERED_SUITE = "eddsa-jcs-2022"

# The responder's clock, supplied rather than read. P-001 §4.3: a runner that
# reads a clock produces an unreproducible result and is non-conforming, and
# §4 step 6's expiry check is the first thing in this pipeline that needs a
# time. The name follows P-007 §4.3's `environment.now`, which is the same
# value reaching the same pipeline one step later.
#
# It sits inside the query's validity window, so every vector below step 6
# passes step 6 rather than rejecting there by accident -- which would make
# each of them assert an ordering it does not test.
ENVIRONMENT = {"now": "2026-07-31T09:01:00Z"}




def signed(query=None, key=REQUESTER, header=None) -> str:
    query = QUERY if query is None else query
    if header is None:
        return av.jws_compact(seed_of(key), key, query)
    return av.jws_with_header(seed_of(key), header, query)


# `routing` is present on every envelope, and after E-38 the reason is no longer
# that a responder might otherwise reject it: §2.1 now says `routing` may be
# absent and a responder must accept a message carrying only `signed`, so a
# conforming one cannot fail these at step 1 for that.
#
# It stays because these vectors assert *where* a request is rejected, and a
# projection is one more thing each of them holds constant. The projection agrees
# with the signed object throughout, so §4 step 8 passes and no vector is wrong
# in a second way. `suite/` covers the routing-less shape.
#
# The expired vector's projection **omits `expires_at`**. §4 step 2 may shed
# obviously stale traffic using that field, and a responder that did would never
# reach the step 6 the vector asserts -- so the one field step 2 reads is the one
# field that projection leaves out. §2.1 permits a strict subset.
def vector(step, name: str, why: str, envelope: dict,
           internal: str, external: str) -> dict:
    return {
        "id": f"ordering/step-{step}/{name}",
        "section": "ordering",
        "requirement": ["core-model.md#4", "core-model.md#5.2.1", "CC-2"],
        "description": why,
        "operation": "process_query",
        "input": {"envelope": envelope, "environment": ENVIRONMENT},
        "expect": {
            "outcome": "rejected",
            "rejection": {
                "internal_reason": internal,
                "wire": {"status": "deny", "external_reason": external},
                "step": step,
            },
            "comparison": "bytes",
        },
    }


def query_with(**changes) -> dict:
    return dict(QUERY, **changes)


def vectors() -> list[dict]:
    valid = signed()
    head, payload, signature = valid.split(".")

    return [
        vector(1, "signed-is-not-a-string",
               "An envelope whose `signed` is a number. Step 1 parses the "
               "envelope before any allocation on attacker-controlled data, so "
               "this is refused before a suite is read or a key resolved — "
               "nothing below step 1 runs.\n\n"
               "**This vector used to carry a `signed` string that was not a "
               "compact serialization**, and that was wrong: `signed` is opaque "
               "at the envelope layer ([P-002](../docs/prds/P-002-message-envelope.md) "
               "§4.4), so step 1 cannot tell one string from another. "
               "[E-46](../docs/open-escalations.md) settled where that case "
               "belongs — step 3, `structurally_invalid`, because the fault is "
               "in the container `crypto-suites.md` §3 defines — and "
               "`suite/verify/not-three-segments` is now the vector for it. The "
               "*type* of `signed` is a fact about the envelope, which is what "
               "makes this one a step-1 case.\n\n"
               "It does **not** cover a transport delivering bytes that are not "
               "JSON at all: a vector file is JSON and a runner is handed a "
               "parsed object, so that case cannot travel through this corpus. "
               "It belongs to the binding that owns framing "
               "([P-013](../docs/prds/P-013-https-binding.md)).",
               {"signed": 3, "routing": ROUTING},
               "envelope_signed_not_a_string", "malformed"),

        vector(3, "unregistered-suite",
               "A header declaring a suite `crypto-suites.md` §3 does not "
               "register. Step 3 reads the declared suite and checks it against "
               "local policy before choosing how to verify, so this rejects "
               "with the signature never checked.",
               {"signed": signed(
                   query_with(signature=dict(QUERY["signature"],
                                             profile=UNREGISTERED_SUITE)),
                   header={"key_id": REQUESTER, "suite": UNREGISTERED_SUITE}),
                "routing": ROUTING},
               "suite_unregistered", "unsupported_suite"),

        vector(4, "signature-from-another-key",
               "A header naming `test-requester-1` over bytes signed by "
               "`test-requester-2`. The key resolves and the signature does "
               "not verify. **Nothing below this line runs for an "
               "unauthenticated request** — so a vector that rejected here for "
               "any later reason would be reporting a check that ran when it "
               "must not have.",
               {"signed": av.jws_compact(seed_of(IMPOSTOR), REQUESTER, QUERY),
                "routing": ROUTING},
               "signature_invalid", "unauthenticated"),

        vector(5, "verified-object-missing-a-required-field",
               "A correctly signed envelope whose core object omits `nonce`, "
               "which §2.2 requires. The signature verifies over exactly these "
               "bytes, so the defect is only visible once the object is parsed "
               "— which §2.1 permits only after verification.",
               {"signed": signed({k: v for k, v in QUERY.items()
                                  if k != "nonce"}),
                "routing": ROUTING},
               "core_object_missing_required_field", "malformed"),

        vector("5a", "header-payload-key-mismatch",
               "A header naming one key over a payload whose "
               "`signature.key_id` names another, signed by the key the header "
               "names — so the signature verifies and only the comparison "
               "fails. It needs the parsed object, so it cannot precede step 5, "
               "and it precedes every step that acts on a payload field.",
               {"signed": signed(query_with(
                   signature=dict(QUERY["signature"], key_id=IMPOSTOR))),
                "routing": ROUTING},
               "header_payload_key_mismatch", "structurally_invalid"),

        vector(6, "expired",
               "A signed request whose `expires_at` has passed. Step 6 is the "
               "**authoritative** expiry check. Its routing projection omits "
               "`expires_at` deliberately: step 2 may shed on that field, "
               "and a responder that did would never reach step 6 — so the "
               "one field step 2 reads is the one this projection leaves "
               "out, which §2.1 permits since `routing` is a strict "
               "subset.",
               {"signed": signed(query_with(
                   issued_at="2026-07-31T08:00:00Z",
                   expires_at="2026-07-31T08:05:00Z")),
                "routing": {k: v for k, v in ROUTING.items()
                            if k != "expires_at"}},
               "request_expired", "expired"),

    ]


def generate() -> dict[Path, str]:
    files = {}
    for body in vectors():
        group, name = body["id"].split("/")[1:]
        files[SECTION / group / f"{name}.json"] = (
            json.dumps(body, indent=2, ensure_ascii=False) + "\n"
        )
    return files


def main(argv: list[str]) -> int:
    checking = "--check" in argv[1:]
    files = generate()

    committed = set(SECTION.rglob("*.json")) if SECTION.is_dir() else set()
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
            print(f"differs from tools/author_ordering.py: {path.relative_to(REPO)}")
        for path in stale:
            print(f"not produced by tools/author_ordering.py: {path.relative_to(REPO)}")
        if differences or stale:
            print(f"\nFAILED: {len(differences) + len(stale)} file(s) out of step — "
                  f"run `python3 tools/author_ordering.py`")
            return 1
        print(f"{len(files)} vector(s) match tools/author_ordering.py")
        return 0

    for path in stale:
        path.unlink()
        print(f"removed (no longer authored): {path.relative_to(REPO)}")
    print(f"wrote {len(differences)} of {len(files)} vector(s) to "
          f"{SECTION.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
