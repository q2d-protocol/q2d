#!/usr/bin/env python3
"""Author the corpus's `suite/` section from the specification text.

    python3 tools/author_suite.py            # write conformance/corpus/suite/
    python3 tools/author_suite.py --check    # fail if what is committed differs

[P-001](../docs/prds/P-001-conformance-corpus.md) §5 gives `suite/` as *"suite
resolution, downgrade rejection, unknown suite"*, and issue 13 authors it.
[P-003](../docs/prds/P-003-crypto-suites.md) §6 names six groups. Four are here
in full; two are not, and neither absence is about this tool — one needs an
operation the vocabulary does not have, the other a second registered suite.

Generated with a `--check`, for the reason
[`author_message.py`](author_message.py) is. The bytes come from
[`author_vectors.py`](author_vectors.py)'s specification-derived signer, and
bytes nobody can re-derive are numbers rather than assertions.

## What a non-conforming producer looks like, and why one is needed

Most of this section asserts what a verifier **refuses**, and every refusal here
needs a message no correct implementation would send: a header carrying `alg`, a
header declaring an unregistered suite, a header naming a key nobody holds.
`jws_with_header` exists for that — the signature is real,
so the message is wrong in exactly the one way the vector names, rather than
being corrupt bytes that would fail for a reason the vector is not about.

That distinction is the whole value of these vectors. A tampered-signature
vector and a wrong-suite vector must fail at different steps for different
reasons, and a message broken in two ways cannot establish which.

## What is not here

**`suite/rfc8032/`** — raw Ed25519 against RFC 8032 §7.1's known answers. There
is no operation for signing a raw message: P-001 §4.5's vocabulary is
protocol-level, and adding one is issue 17's, which settles vocabulary additions
as a single change. The known answers are not unchecked meanwhile —
[`author_vectors.py`](author_vectors.py) refuses to sign anything until it
reproduces all three, so every byte this file emits already depends on them.

**`suite/status/`**, and `suite/downgrade/`'s below-floor case — both need a
second registered suite. [`crypto-suites.md`](../spec/crypto-suites.md) §3
registers exactly one, `eddsa-jws-2026`, and it is `active`: nothing is
deprecated to verify-but-not-produce, nothing is withdrawn, and no suite sits
below a plausible floor. These land when a second suite does, and the
unregistered-suite vector below covers the part that does not need one.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import author_vectors as av  # noqa: E402
from author_message import QUERY, ROUTING, REQUESTER, IMPOSTOR, seed_of  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
SECTION = REPO / "conformance" / "corpus" / "suite"

# A key no `conformance/keys/` entry names, so `resolve_key` fails rather than
# returning a key the signature then fails against. §5.2.1 collapses the two
# into `unauthenticated`, which is what `suite/keys/` asserts.
UNKNOWN_KEY = "test-requester-absent"

# An identifier `crypto-suites.md` §3 does not register. Deliberately shaped
# like a real one: a verifier must reject it because it is not in the registry,
# not because it fails to parse.
UNREGISTERED_SUITE = "eddsa-jcs-2022"

# `message/sign/query-minimal`'s query under the other requester key. The
# payload's `signature.key_id` moves with the header's, because a payload naming
# one key under a header naming another is precisely the mismatch P-003 §4.2
# step 4 rejects -- a "valid" vector must not be one of E-34's cases by
# accident.
SECOND_KEY_QUERY = dict(
    QUERY, signature=dict(QUERY["signature"], key_id=IMPOSTOR))


def rejects(internal: str, external: str, step=None) -> dict:
    """A rejection asserting both halves, with `wire` as a projection.

    These vectors test suite resolution and verification, not response
    construction, so the projection asserts `status` and `external_reason` and
    nothing about the receipt (P-001 §4.4). `bytes`, because §6 makes a
    normalized denial's uniformity structural and declaring `semantic` would say
    the specification requires no determinism here.
    """
    rejection = {
        "internal_reason": internal,
        "wire": {"status": "deny", "external_reason": external},
    }
    # A step is asserted only where §4 determines one. `fold_registry.py` set
    # this precedent for `constraint_violation_minimum_slot_duration` before §4
    # gained step 11a: a step-less vector asserts no ordering (P-001 §4.8),
    # which is weaker and true, where a guessed step is stronger and wrong.
    if step is not None:
        rejection["step"] = step
    return {"outcome": "rejected", "rejection": rejection, "comparison": "bytes"}


def envelope(signed: str) -> dict:
    """An envelope carrying both of §2.1's parts.

    These vectors omitted `routing` until E-38 was raised, on the reasoning
    that it is advisory, that §4 step 8 compares only what is present, and that
    a projection would give each vector a second way to fail. The first two are
    true and the conclusion did not follow: §2.1 opens *"a message has two
    parts"*, and *advisory* answers what `routing` may be used for rather than
    whether it may be absent.

    The third reason was the real one, and it is answered rather than
    contradicted: the projection here is **correct** for `QUERY`, so it agrees
    with `signed` and step 8 passes. A vector fails on its suite defect, which
    is what it is for.

    E-38 is open and recommends the other answer. If it closes that way this
    goes back to one member and these ten vectors change again — which is
    exactly why the tool regenerates them rather than anyone editing bytes.
    """
    return {"envelope": {"signed": signed, "routing": ROUTING}}


def vectors() -> list[dict]:
    seed = seed_of(REQUESTER)
    valid = av.jws_compact(seed, REQUESTER, QUERY)
    head, payload, signature = valid.split(".")

    return [
        {
            "id": "suite/sign/second-key",
            "section": "suite",
            "requirement": ["crypto-suites.md#3", "core-model.md#2.7"],
            "description": (
                "The same query `message/sign/query-minimal` signs, under a "
                "different key — `signature.key_id` in the payload moved with "
                "it, since a payload naming one key under a header naming "
                "another is the mismatch P-003 §4.2 step 4 rejects. Byte-exact, "
                "and distinct from that vector in exactly one input, so a "
                "defect in how a key reaches the signature shows here and not "
                "there."
            ),
            "operation": "sign_query",
            "input": {"key_id": IMPOSTOR, "query": SECOND_KEY_QUERY},
            "expect": {
                "outcome": "ok",
                "output": av.jws_compact(seed_of(IMPOSTOR), IMPOSTOR,
                                         SECOND_KEY_QUERY),
                "comparison": "bytes",
            },
        },
        {
            "id": "suite/verify/valid",
            "section": "suite",
            "requirement": ["crypto-suites.md#3", "core-model.md#4"],
            "description": (
                "The conforming case, which the rejections below are only "
                "meaningful against: same key, same payload, header carrying "
                "`suite` and `key_id` and nothing else."
            ),
            "operation": "verify_query",
            "input": envelope(valid),
            "expect": {"outcome": "ok", "output": QUERY, "comparison": "semantic"},
        },
        {
            "id": "suite/verify/tampered-payload",
            "section": "suite",
            "requirement": ["crypto-suites.md#3", "core-model.md#4",
                            "core-model.md#5.2.1"],
            "description": (
                "The payload segment of a valid string, altered by one "
                "character. The signature covers the exact transmitted bytes "
                "(crypto-suites.md §3), so verification fails at §4 step 4 — "
                "before the object is parsed, which is why a malformed payload "
                "is not what this reports."
            ),
            "operation": "verify_query",
            "input": envelope(f"{head}.{payload[:-1]}{'A' if payload[-1] != 'A' else 'B'}.{signature}"),
            "expect": rejects("signature_invalid", "unauthenticated", 4),
        },
        {
            "id": "suite/verify/tampered-signature",
            "section": "suite",
            "requirement": ["crypto-suites.md#3", "core-model.md#4",
                            "core-model.md#5.2.1"],
            "description": (
                "The signature segment altered by one character, over an "
                "untouched header and payload. §5.2.1 gives one class for the "
                "whole of authentication, so this reaches the same "
                "`external_reason` as the tampered payload above while the "
                "responder records a different internal reason. That the two "
                "are *indistinguishable* is more than this asserts: the wire "
                "here is a projection, and the whole response — receipt and "
                "signature included — is `denial/`'s to compare."
            ),
            "operation": "verify_query",
            "input": envelope(f"{head}.{payload}.{signature[:-1]}{'A' if signature[-1] != 'A' else 'B'}"),
            "expect": rejects("signature_invalid", "unauthenticated", 4),
        },
        {
            "id": "suite/verify/tampered-header",
            "section": "suite",
            "requirement": ["crypto-suites.md#3", "core-model.md#4",
                            "core-model.md#5.2.1"],
            "description": (
                "The header segment replaced with one naming a different key, "
                "over an untouched payload and the original signature. The "
                "protected header is covered by the signature (P-003 §4.1), so "
                "altering it invalidates the signature — the named key resolves, "
                "and verification fails against it at §4 step 4."
            ),
            "operation": "verify_query",
            "input": envelope(
                av.base64url(av.serialize({"key_id": IMPOSTOR, "suite": av.SUITE}))
                + f".{payload}.{signature}"),
            "expect": rejects("signature_invalid", "unauthenticated", 4),
        },
        {
            "id": "suite/downgrade/unregistered-suite",
            "section": "suite",
            "requirement": ["crypto-suites.md#3", "core-model.md#4",
                            "core-model.md#5.2.1"],
            "description": (
                f"A header declaring `{UNREGISTERED_SUITE}`, which "
                "crypto-suites.md §3 does not register — it is the suite the "
                "deposited report's example used, and §3 declined to register "
                "any JCS-based suite. Rejected at §4 step 3, before "
                "verification: the declared suite selects how to verify, so it "
                "is checked against local policy first."
            ),
            "operation": "verify_query",
            "input": envelope(av.jws_with_header(
                seed, {"key_id": REQUESTER, "suite": UNREGISTERED_SUITE},
                dict(QUERY, signature=dict(QUERY["signature"],
                                           profile=UNREGISTERED_SUITE)))),
            "expect": rejects("suite_unregistered", "unsupported_suite", 3),
        },
        {
            "id": "suite/downgrade/header-carries-alg",
            "section": "suite",
            "requirement": ["crypto-suites.md#3", "core-model.md#4",
                            "core-model.md#5.2.1"],
            "description": (
                "A header carrying `alg` alongside `suite` and `key_id`. §3 "
                "closes the header at two members: one carrying `alg` is one a "
                "general-purpose JOSE library could process, and such a library "
                "selects its algorithm from the header — the decision §4's "
                "suite-policy check exists to take away from the sender. "
                "`structurally_invalid` rather than `unsupported_suite`: the "
                "declared suite is the registered one, which is why the message "
                "got this far (E-34)."
            ),
            "operation": "verify_query",
            "input": envelope(av.jws_with_header(
                seed,
                {"alg": "EdDSA", "key_id": REQUESTER, "suite": av.SUITE},
                QUERY)),
            "expect": rejects("header_member_not_permitted",
                              "structurally_invalid", 3),
        },
        {
            "id": "suite/downgrade/header-payload-suite-mismatch",
            "section": "suite",
            "requirement": ["crypto-suites.md#3", "core-model.md#2.7",
                            "core-model.md#5.2.1"],
            "description": (
                "A header declaring the registered suite over a payload whose "
                "`signature.profile` declares another. The signature verifies — "
                "the verifier used the header's suite — so this is caught after "
                "verification by P-003 §4.2 step 4, which is the point: the "
                "payload's copy is authoritative, the header's is not, and "
                "comparing them catches a producer no verifier would otherwise "
                "notice. §4 step **5a** is where it happens — the comparison "
                "needs the parsed payload, so it cannot precede step 5, and "
                "E-35 added the step for symmetry with the response order's "
                "4a."
            ),
            "operation": "verify_query",
            "input": envelope(av.jws_compact(
                seed, REQUESTER,
                dict(QUERY, signature=dict(QUERY["signature"],
                                           profile=UNREGISTERED_SUITE)))),
            "expect": rejects("header_payload_suite_mismatch", "structurally_invalid", "5a"),
        },
        {
            "id": "suite/downgrade/header-payload-key-mismatch",
            "section": "suite",
            "requirement": ["crypto-suites.md#3", "core-model.md#2.7",
                            "core-model.md#5.2.1"],
            "description": (
                "A header naming one key over a payload whose "
                "`signature.key_id` names another, signed by the key the header "
                "names — so the signature verifies and only the comparison "
                "fails. The same `external_reason` as the suite mismatch above: "
                "§5.2.1 gives one value for all three structural failures, "
                "because which part disagreed is visible in the message the "
                "requester itself produced."
            ),
            "operation": "verify_query",
            "input": envelope(av.jws_compact(
                seed, REQUESTER,
                dict(QUERY, signature=dict(QUERY["signature"],
                                           key_id=IMPOSTOR)))),
            "expect": rejects("header_payload_key_mismatch", "structurally_invalid", "5a"),
        },
        {
            "id": "suite/keys/unresolvable",
            "section": "suite",
            "requirement": ["core-model.md#2.3", "core-model.md#4",
                            "core-model.md#5.2.1"],
            "description": (
                "A header naming a key no verifier holds. `resolve_key` fails "
                "at §4 step 4, and the requester receives what an invalid "
                "signature produces — §5.2.1 collapses them so that a requester "
                "cannot probe which identities a custodian holds, which is the "
                "one thing distinguishing them would reveal."
            ),
            "operation": "verify_query",
            "input": envelope(av.jws_with_header(
                seed, {"key_id": UNKNOWN_KEY, "suite": av.SUITE},
                dict(QUERY, signature=dict(QUERY["signature"],
                                           key_id=UNKNOWN_KEY)))),
            "expect": rejects("key_unresolvable", "unauthenticated", 4),
        },
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
            print(f"differs from tools/author_suite.py: {path.relative_to(REPO)}")
        for path in stale:
            print(f"not produced by tools/author_suite.py: {path.relative_to(REPO)}")
        if differences or stale:
            print(f"\nFAILED: {len(differences) + len(stale)} file(s) out of step — "
                  f"run `python3 tools/author_suite.py`")
            return 1
        print(f"{len(files)} vector(s) match tools/author_suite.py")
        return 0

    for path in stale:
        path.unlink()
        print(f"removed (no longer authored): {path.relative_to(REPO)}")
    print(f"wrote {len(differences)} of {len(files)} vector(s) to "
          f"{SECTION.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
