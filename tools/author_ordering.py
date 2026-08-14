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

## What is here, and what is not

A vector's `input` has to carry everything the operation needs (P-001 §4.3), and
for the pipeline that means responder-side state. Where that state is a **pinned
registry**, it is in hand: `registry/manifest.json` is what a runner embeds, so
every step from 10 to 13 is expressible today. Where it is anything else, the
fixture format belongs to the PRD that defines the state, and none exists yet:

| Step | Needs | Owner |
|---|---|---|
| 7 | a delegation profile and evidence | [P-014](../docs/prds/P-014-identity-pairing.md) |
| 9 | a replay cache with a prior entry | [P-004](../docs/prds/P-004-replay-idempotency.md) |
| 9a | a configured rate limit | [P-004](../docs/prds/P-004-replay-idempotency.md), [P-008](../docs/prds/P-008-capacity-accounting.md) |
| 14 | a fixture rule set | [P-007](../docs/prds/P-007-policy-engine.md) |
| 15 | budget state | [P-008](../docs/prds/P-008-capacity-accounting.md) |

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
# `registry/manifest.json` declares one external class for everything its
# entries govern. Steps 10 onward are Tier C, so they all carry it -- which is
# the point of the class rather than a limitation of these vectors.
TIER_C = "unavailable"


def signed(query=None, key=REQUESTER, header=None) -> str:
    query = QUERY if query is None else query
    if header is None:
        return av.jws_compact(seed_of(key), key, query)
    return av.jws_with_header(seed_of(key), header, query)


def vector(step, name: str, why: str, envelope: dict,
           internal: str, external: str) -> dict:
    return {
        "id": f"ordering/step-{step}/{name}",
        "section": "ordering",
        "requirement": ["core-model.md#4", "core-model.md#5.2.1", "CC-2"],
        "description": why,
        "operation": "process_query",
        "input": {"envelope": envelope},
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
        vector(1, "envelope-not-json",
               "An envelope that is not JSON at all. Step 1 parses the envelope "
               "before any allocation on attacker-controlled data, so this is "
               "refused before a suite is read or a key resolved — nothing "
               "below step 1 runs.",
               {"signed": "not-a-compact-serialization"},
               "envelope_malformed", "malformed"),

        vector(3, "unregistered-suite",
               "A header declaring a suite `crypto-suites.md` §3 does not "
               "register. Step 3 reads the declared suite and checks it against "
               "local policy before choosing how to verify, so this rejects "
               "with the signature never checked.",
               {"signed": signed(
                   query_with(signature=dict(QUERY["signature"],
                                             profile=UNREGISTERED_SUITE)),
                   header={"key_id": REQUESTER, "suite": UNREGISTERED_SUITE})},
               "suite_unregistered", "unsupported_suite"),

        vector(4, "signature-from-another-key",
               "A header naming `test-requester-1` over bytes signed by "
               "`test-requester-2`. The key resolves and the signature does "
               "not verify. **Nothing below this line runs for an "
               "unauthenticated request** — so a vector that rejected here for "
               "any later reason would be reporting a check that ran when it "
               "must not have.",
               {"signed": av.jws_compact(seed_of(IMPOSTOR), REQUESTER, QUERY)},
               "signature_invalid", "unauthenticated"),

        vector(5, "verified-object-missing-a-required-field",
               "A correctly signed envelope whose core object omits `nonce`, "
               "which §2.2 requires. The signature verifies over exactly these "
               "bytes, so the defect is only visible once the object is parsed "
               "— which §2.1 permits only after verification.",
               {"signed": signed({k: v for k, v in QUERY.items()
                                  if k != "nonce"})},
               "core_object_missing_required_field", "malformed"),

        vector("5a", "header-payload-key-mismatch",
               "A header naming one key over a payload whose "
               "`signature.key_id` names another, signed by the key the header "
               "names — so the signature verifies and only the comparison "
               "fails. It needs the parsed object, so it cannot precede step 5, "
               "and it precedes every step that acts on a payload field.",
               {"signed": signed(query_with(
                   signature=dict(QUERY["signature"], key_id=IMPOSTOR)))},
               "header_payload_key_mismatch", "structurally_invalid"),

        vector(6, "expired",
               "A signed request whose `expires_at` has passed. Step 6 is the "
               "**authoritative** expiry check — step 2 may shed on "
               "`routing.expires_at` first, but that is advisory, and a "
               "responder that skips it must still reject here.",
               {"signed": signed(query_with(
                   issued_at="2026-07-31T08:00:00Z",
                   expires_at="2026-07-31T08:05:00Z"))},
               "request_expired", "expired"),

        vector(8, "routing-disagrees",
               "A routing projection whose `expires_at` differs from the "
               "verified object's. Step 8 runs after verification, so a "
               "disagreement is judged against a signed value rather than "
               "against another piece of attacker-controlled data.",
               {"signed": valid,
                "routing": dict(ROUTING, expires_at="2026-07-31T09:05:01Z")},
               "routing_signed_mismatch", "routing_mismatch"),

        vector(10, "unknown-predicate",
               "A predicate identifier no entry in the pinned registry "
               "declares. Step 10 fails closed on anything unrecognized, and "
               "the requester receives the registry's declared class — the "
               "same one a policy refusal produces at step 14, so reaching "
               "either tells a requester nothing about how far it got.",
               {"signed": signed(query_with(predicate=dict(
                   QUERY["predicate"],
                   id="https://q2d.dev/predicates/dietary/not-registered")))},
               "predicate_unknown", TIER_C),

        vector(11, "public-context-fails-the-entry-schema",
               "An empty `menu`, where the entry's input schema requires at "
               "least one item. The schema comes from the registry rather than "
               "from the request, which is why this cannot be checked before "
               "step 10 resolved the entry.",
               {"signed": signed(query_with(predicate=dict(
                   QUERY["predicate"], public_context={"menu": []})))},
               "public_context_schema_violation", TIER_C),

        vector(12, "contract-broader-than-the-entry",
               "An answer contract requesting a `scalar` where the entry's "
               "registered release shape is `boolean` — broader than the entry "
               "permits, which Q2D-C-02 refuses. After step 11, because a "
               "contract is judged against an entry that has been resolved and "
               "whose public context has been validated.",
               {"signed": signed(query_with(answer_contract=dict(
                   QUERY["answer_contract"], release_shape="scalar")))},
               "contract_not_narrowable", TIER_C),

        vector(13, "unsupported-assurance-profile",
               "A requested assurance profile the entry does not support. "
               "§4 step 13 refuses rather than downgrading, and it is the last "
               "step before policy is consulted — so a request refused here "
               "has reached no policy authority.",
               {"signed": signed(query_with(predicate=dict(
                   QUERY["predicate"],
                   requested_assurance="attested-enclave-0.1")))},
               "assurance_profile_unsupported", TIER_C),
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
