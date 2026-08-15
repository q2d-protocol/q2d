#!/usr/bin/env python3
"""Author the corpus's `message/` section from the specification text.

    python3 tools/author_message.py            # write conformance/corpus/message/
    python3 tools/author_message.py --check    # fail if what is committed differs

[P-001](../docs/prds/P-001-conformance-corpus.md) §5 gives `message/` as
*"envelope construction, signing, verification, routing projection,
routing/signed disagreement"*, and issue 12 authors it.

**Generated rather than hand-written, for the same reason
[`fold_registry.py`](fold_registry.py) is.** A `message/sign/` vector asserts the
exact bytes a conforming implementation produces, and those bytes come from
[`author_vectors.py`](author_vectors.py) — the specification-derived serializer
and signer. Committing them without a way to reproduce them would make the
corpus a set of numbers nobody can re-derive; `--check` in CI turns a divergence
into a failing build instead.

The vectors are still **authored data**: an implementation is compared against
what is committed, not against whatever this file produces today. The check
exists so the two cannot drift silently, not so the corpus is regenerated on
demand.

## What is here

Signing, verification, and the routing projection — positive and negative both,
since [CLAUDE.md](../CLAUDE.md) is explicit that the interesting behaviour of
this protocol is what it refuses. The rejections wait on nothing now:
[`core-model.md`](../spec/core-model.md) §5.2.1 enumerates the `external_reason`
vocabulary, so a vector can say what a requester receives (E-33).

**No vector here cites a claim, and that is deliberate.**
[`claims.md`](../spec/claims.md) Q2D-C-05 — request binding — is the claim this
section is closest to, and its own *Verified by* names three vectors:
`field-tampering`, `routing-mismatch`, `suite-downgrade`. All three are
rejections, none exists, and none of these is one of them. Citing the claim would
make `harness coverage` report it as covered while everything that verifies it is
unbuilt, which is the overstatement `claims.md` exists to prevent. These vectors
cite the specification sections they exercise instead.

**Each rejection asserts both halves.** The internal reason is what an
implementation records locally and the wire response is what a requester
receives, and they are separate values in a conforming implementation — a runner
deriving one from the other has already lost the property the corpus is checking
(P-001 §4.6).

The `wire` here is a **projection**: `status` and `external_reason`, and nothing
about the receipt or the signature. These vectors test verification and the
routing comparison, not response construction, and a vector asserting a subset
asserts nothing about the fields it omits (P-001 §4.4). `denial/` is where a
whole normalized response is asserted, and it may not project — which is P-009's
section to author, not this one.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import author_vectors as av  # noqa: E402  (after sys.path)

REPO = Path(__file__).resolve().parent.parent
SECTION = REPO / "conformance" / "corpus" / "message"

REQUESTER = "test-requester-1"
# The vector that presents a signature from a key the header does not name.
# `conformance/keys/README.md`: test-requester-2 "exists so a vector can present
# a signature from the wrong key, which is a rejection the corpus has to
# contain".
IMPOSTOR = "test-requester-2"

# One query, used by every vector in the section. Every field
# `core-model.md` §2.2-§2.7 marks required is present and no optional one is,
# so the bytes are the smallest a conforming requester produces -- an optional
# field would be asserting that implementations agree about something no
# requester has to send.
#
# `signature.value` is absent: `crypto-suites.md` §3 puts it in the compact
# form's third segment, so a payload carrying it would sign itself (E-31).
# `signature.profile` and `signature.key_id` are present, and §4 step 4's
# sibling in P-003 §4.2 compares both against the protected header.
#
# `answer_contract` carries no `maximum_cardinality`: §2.5 makes that field
# `set`-only (E-29), and this is a `boolean`. No `precision`, which is for
# `scalar` and `interval`; no `coarsening`, which an `enum` request declares.
QUERY = {
    "q2d_version": "0.1",
    "type": "query",
    "query_id": "urn:uuid:0e183389-0f37-4c5f-8c56-1ea7e5818e18",
    "issued_at": "2026-07-31T09:00:00Z",
    "expires_at": "2026-07-31T09:05:00Z",
    "nonce": "Ux7kFQ2mS0aVvJ1cPzN4bw",
    "requester": {
        "principal": "did:key:z6MkRequesterPrincipal",
        "agent": "did:key:z6MkRequesterAgent",
        "delegation": {"profile": "local-pairing-0.1", "reference": "sha256:7ef1"},
    },
    "target": {"custodian": "https://friend.example/.well-known/q2d"},
    "predicate": {
        "id": "https://q2d.dev/predicates/dietary/menu-compatible",
        "version": "0.1",
        # The reference manifest's entry digest for that predicate, so a
        # responder resolving it against `registry/manifest.json` finds the
        # entry this query was built against (§2.4.1).
        "registry_digest": (
            "sha256:bd08ff230de0d8ce34de99967f7a9097988b49058f0a21dd35b9444c24098e35"
        ),
        "public_context": {
            "menu": [
                {"item_id": "risotto", "contains": ["milk"]},
                {"item_id": "salad", "contains": []},
            ]
        },
    },
    "answer_contract": {
        "release_shape": "boolean",
        "domain": [False, True],
        "allowed_detail_fields": [],
    },
    "purpose": {
        "code": "social.meal-planning",
        "description": "Choose a dinner venue for 2026-07-31",
    },
    "delivery": {
        "answer_recipient": "did:key:z6MkRequesterRuntime",
        "permitted_sinks": ["urn:q2d:sink:model:local"],
    },
    "signature": {"profile": av.SUITE, "key_id": REQUESTER},
}

# `core-model.md` §2.1: `routing` carries at most these six, and each must equal
# the verified object's exactly. Purpose, sinks, subjects, the answer contract
# and public context are never projected.
ROUTING = {
    "q2d_version": QUERY["q2d_version"],
    "type": QUERY["type"],
    "target": {"custodian": QUERY["target"]["custodian"]},
    "predicate": {
        "id": QUERY["predicate"]["id"],
        "version": QUERY["predicate"]["version"],
    },
    "expires_at": QUERY["expires_at"],
}


def seed_of(key_id: str) -> bytes:
    keys = json.loads(av.KEY_FILE.read_text(encoding="utf-8"))["keys"]
    return bytes.fromhex(keys[key_id]["seed"])


def signed_query() -> str:
    return av.jws_compact(seed_of(REQUESTER), REQUESTER, QUERY)


def signed_by_impostor() -> str:
    """The same query, header naming `test-requester-1`, signed by the other key.

    `jws_compact` puts `key_id` in the header, so passing one key's identifier
    and another's seed produces exactly the message a forger sends: a header
    naming a key the verifier trusts, over bytes that key did not sign. The
    signature fails at §4 step 4 -- `unauthenticated`, since §5.2.1 collapses an
    invalid signature with an unresolvable key.
    """
    return av.jws_compact(seed_of(IMPOSTOR), REQUESTER, QUERY)


# A rejection asserts what the requester receives, and these vectors are about
# verification rather than response construction -- so `wire` is a projection of
# §5.2's response, `status` and `external_reason` only, asserting nothing about
# the fields it omits (P-001 §4.4).
def rejects(internal: str, external: str, step) -> dict:
    return {
        "outcome": "rejected",
        "rejection": {
            "internal_reason": internal,
            "wire": {"status": "deny", "external_reason": external},
            "step": step,
        },
        # `bytes`: §6 makes a normalized denial's uniformity structural, and
        # §4.4 reserves `bytes` for where the specification requires
        # determinism. Declaring `semantic` would say it requires none here.
        "comparison": "bytes",
    }


def with_public_context(context: dict) -> dict:
    """`QUERY` with its public context replaced.

    `sign_query` signs; it does not resolve a predicate, so nothing here is
    validated against `menu_compatible`'s schema and these contexts are
    deliberately shapes no registered entry declares. That is the point:
    serialization.md §1's
    edges are not reachable through a schema-valid public context, because no
    entry has a reason to declare a supplementary-plane key or an `i64`
    boundary — which is exactly why `testdata/profile-edges` exists and why
    these vectors carry the same shapes into the shared corpus.
    """
    query = json.loads(json.dumps(QUERY))
    query["predicate"]["public_context"] = context
    return query


def serialize_vector(name: str, requirement: list[str], description: str,
                     context: dict) -> dict:
    """A `sign_query` vector whose expectation is the compact bytes.

    serialization.md §1 has no operation of its own and needs none: a signature
    covers the
    exact transmitted bytes, so a vector asserting the compact string asserts
    the serialization that produced it. A wrong key order or a stray escape
    changes the payload segment and the vector fails on the byte comparison.

    Each traces to `crypto-suites.md` §3, which is the requirement these
    actually test: **both implementations must produce identical bytes for the
    same message.** The profile that delivers it is serialization.md §1, and a
    vector's
    `requirement` list cites `spec/` rather than a PRD — so the citation is the
    obligation, not the mechanism. The second entry is where the *shape* being
    serialized comes from: §2.4 for a public context, `scope.md` §4.1 for the
    integer range.

    §2.4 is cited for *where the shape comes from* — it lists `public_context`
    as the predicate's own input — and not as a constraint on it. The
    constraint is `scope.md` §4.1's schema profile, and neither section defines
    the serialization: that is `crypto-suites.md` §3's identical-bytes rule,
    which is why it leads every list here.
    """
    query = with_public_context(context)
    return {
        "id": f"message/serialize/{name}",
        "section": "message",
        "requirement": requirement,
        "description": description,
        "operation": "sign_query",
        "input": {"key_id": REQUESTER, "query": query},
        "expect": {
            "outcome": "ok",
            "output": av.jws_compact(seed_of(REQUESTER), REQUESTER, query),
            "comparison": "bytes",
        },
    }


def serialize_vectors() -> list[dict]:
    return [
        serialize_vector(
            "key-order-above-the-bmp",
            ["serialization.md#1", "crypto-suites.md#3", "core-model.md#2.4"],
            "Object keys sorted by **UTF-16 code unit**, which differs from "
            "Unicode scalar order above the BMP: U+10000 encodes as the "
            "surrogate pair D800 DC00 and therefore sorts below U+FFFD, where "
            "scalar order puts it above. A serializer using its language's "
            "default string ordering — Rust's `BTreeMap`, Go's byte comparison "
            "— produces the other order and fails here. No field name in "
            "`core-model.md` §2 is outside ASCII, so this is unreachable "
            "except through a predicate's own public context, whose shape §2.4 "
            "leaves to the registered predicate and whose length "
            "[`scope.md`](../spec/scope.md) §4.1 bounds.",
            {"\U00010000": "supplementary", "\uFFFD": "bmp", "a": "ascii"},
        ),
        serialize_vector(
            "escapes-and-what-must-not-be-escaped",
            ["serialization.md#1", "crypto-suites.md#3", "core-model.md#2.4"],
            "Minimal escaping. The two RFC 8259 requires and the five "
            "two-character forms it names are escaped; a control character "
            "with no short form takes `\\u0001` in lowercase hex; and `<`, "
            "`>`, `&` and `/` are **not** escaped, which is where Go's "
            "`encoding/json` differs by default and would produce different "
            "bytes for the same message.",
            {
                "escapes": "\"\\\b\f\n\r\t\u0001",
                "unescaped": "<a>&b'c/d",
                "direct": "\u00e9\U0001F600\u65e5\u672c\u8a9e",
            },
        ),
        serialize_vector(
            "integer-boundaries",
            ["serialization.md#1", "crypto-suites.md#3", "scope.md#4.1"],
            "Integers with no exponent, no leading `+` and no leading zeros, "
            "at both ends of the range `scope.md` §4.1 requires an entry's "
            "integers to lie within. A serializer that rendered these through "
            "a float — or a parser that read them into one — loses the low "
            "bits above 2^53 and produces different bytes, which is the "
            "hazard `crypto-suites.md` §3 cites against a JCS-based suite.",
            {"max": 2**63 - 1, "min": -(2**63), "just_past_2_53": 2**53 + 1,
             "zero": 0, "negative": -1},
        ),
        serialize_vector(
            "empty-containers-and-a-present-null",
            ["serialization.md#1", "crypto-suites.md#3", "core-model.md#2.4"],
            "An empty object, an empty array, and a field explicitly set to "
            "null — each with one serialization and no other. "
            "serialization.md §1 omits an "
            "*absent* optional rather than nulling it, so a present null and "
            "an absent field are different documents; this vector carries the "
            "present one, and `message/sign/query-minimal` is the query with "
            "every optional absent.",
            {"empty_object": {}, "empty_array": [], "explicit_null": None,
             "nested": {"z": {"y": [{"x": 1}]}}},
        ),
    ]


def reject_vector(name: str, requirement: list[str], description: str,
                  signed: str, internal: str) -> dict:
    """A `verify_query` vector whose payload is wrong in one stated way.

    Every one is **validly signed**. A vector whose bytes were corrupt would
    fail at step 4 for a reason it is not about, and would pass an
    implementation that never reached the defect — so the signature is over
    exactly the payload the vector is asserting a parser refuses.

    All of these are §5.2.1's `malformed` on the wire: *the verified core
    object malformed, or missing a field §2 requires*. The internal reasons
    differ because an operator needs to know which, and `denial/`'s uniformity
    assertion is what proves the wire response does not.
    """
    return {
        "id": f"message/reject/{name}",
        "section": "message",
        "requirement": requirement,
        "description": description,
        "operation": "verify_query",
        "input": {"envelope": {"signed": signed, "routing": ROUTING}},
        "expect": {
            "outcome": "rejected",
            "rejection": {
                "internal_reason": internal,
                "wire": {"status": "deny", "external_reason": "malformed"},
                "step": 5,
            },
            "comparison": "bytes",
        },
    }


def payload_bytes(replacement: str) -> bytes:
    """`QUERY`'s serialization with one member replaced by raw text.

    Built from the profile's own output and edited, rather than assembled by
    hand, so the vector differs from a conforming payload in exactly the way it
    names and in nothing else — same field order, same escaping, same
    everything a byte comparison would otherwise catch.
    """
    conforming = av.serialize(QUERY).decode("utf-8")
    marker = '"nonce":"' + QUERY["nonce"] + '"'
    assert conforming.count(marker) == 1, "the nonce is where this edit anchors"
    return conforming.replace(marker, replacement).encode("utf-8")


def reject_vectors() -> list[dict]:
    seed = seed_of(REQUESTER)

    duplicate = av.jws_over_payload_bytes(
        seed, REQUESTER,
        payload_bytes('"nonce":"' + QUERY["nonce"] + '","nonce":"Ux7kFQ2mS0aVvJ1cPzN4bx"'))
    a_float = av.jws_over_payload_bytes(
        seed, REQUESTER,
        payload_bytes('"nonce":"' + QUERY["nonce"] + '","capacity_millibits":1.5'))

    deep = json.loads(json.dumps(QUERY))
    nest = {"bottom": True}
    for _ in range(20):
        nest = {"deeper": nest}
    deep["predicate"]["public_context"] = nest

    wide = json.loads(json.dumps(QUERY))
    wide["predicate"]["public_context"] = {f"k{i:03d}": i for i in range(65)}

    long_string = json.loads(json.dumps(QUERY))
    long_string["nonce"] = "n" * 2100

    old_version = json.loads(json.dumps(QUERY))
    old_version["q2d_version"] = "0.2"

    return [
        reject_vector(
            "duplicate-key",
            ["serialization.md#2"],
            "A payload carrying `nonce` twice. serialization.md §2 rejects a "
            "duplicate key rather than resolving it, and the reason is that "
            "the alternatives are worse than a refusal: a parser taking "
            "last-wins and one taking first-wins read **one signed payload two "
            "ways**, and both readings carry a valid signature. Go's "
            "`encoding/json` takes last-wins silently, which is why this vector "
            "exists rather than being assumed. The payload is supplied as bytes "
            "because no JSON object can hold the defect.",
            duplicate, "core_object_duplicate_key"),
        reject_vector(
            "float-in-the-payload",
            ["serialization.md#1", "serialization.md#2"],
            "A payload carrying `1.5`. serialization.md §1 admits no "
            "floating-point in a signed structure — capacity is integer "
            "millibits, timestamps are "
            "strings — because IEEE-754 rendering differs between languages and "
            "one float field would make two implementations emit different "
            "bytes for the same message. Refused **syntactically**, on the "
            "fraction rather than on the value: deciding that `1e2` is a "
            "hundred means exponent arithmetic, and with `1e400`, arithmetic in "
            "what. Supplied as bytes because the authoring tool refuses to "
            "serialize a float at all.",
            a_float, "core_object_float"),
        reject_vector(
            "nesting-past-the-limit",
            ["core-model.md#2.8"],
            "A public context nested twenty deep, past §2.8's sixteen. The "
            "limit is normative rather than advisory: a limit an implementation "
            "may choose is not a limit, and §1 admits no round trip in which a "
            "requester could discover which one it is addressing. Unbounded "
            "recursive descent is also a stack overflow, and a crash is not a "
            "rejection.",
            av.jws_compact(seed, REQUESTER, deep), "core_object_too_deep"),
        reject_vector(
            "too-many-members",
            ["core-model.md#2.8"],
            "An object of sixty-five members, past §2.8's sixty-four. Counted "
            "per object rather than per message, so a payload may hold many "
            "objects and none of them may be wide.",
            av.jws_compact(seed, REQUESTER, wide), "core_object_too_many_members"),
        reject_vector(
            "string-past-the-limit",
            ["core-model.md#2.8"],
            "A `nonce` of 2100 bytes, past §2.8's 2 KiB. A **protocol** field, "
            "deliberately: §2.8's string limit covers the fields the "
            "specification defines and stops at `predicate.public_context`, so "
            "a vector using a predicate's own field would assert the opposite "
            "of the rule.",
            av.jws_compact(seed, REQUESTER, long_string), "core_object_string_too_long"),
    ] + [
        {
            "id": "message/reject/unknown-version",
            "section": "message",
            "requirement": ["core-model.md#4", "core-model.md#5.2.1"],
            "description": (
                "A payload declaring `q2d_version` 0.2. The **only** vector in "
                "this group whose wire response is not `malformed`: §5.2.1 "
                "gives `unsupported_version` its own row, and an absent or "
                "non-string version would be `malformed` instead — *missing a "
                "field §2 requires*. The internal reason is a different string "
                "from the external one even here, where the wire value has the "
                "same name: they are separate values, and equal halves would "
                "assert the leak rather than the separation. A responder rejects without interpreting "
                "anything else, because version 0.2 may have moved or retyped "
                "any field and a diagnostic built by reading them is a guess "
                "presented as fact."
            ),
            "operation": "verify_query",
            "input": {"envelope": {"signed": av.jws_compact(seed, REQUESTER, old_version),
                                   "routing": dict(ROUTING, q2d_version="0.2")}},
            "expect": {
                "outcome": "rejected",
                "rejection": {
                    # Not `unsupported_version`, which is the *external*
                    # value. They are separate values (P-001 §4.6), and a
                    # vector whose two halves were equal would assert the leak
                    # rather than the separation — `test_message_section.py`
                    # holds every rejection here to that, and caught this one.
                    "internal_reason": "core_object_unsupported_version",
                    "wire": {"status": "deny", "external_reason": "unsupported_version"},
                    "step": 5,
                },
                "comparison": "bytes",
            },
        },
    ]


def vectors() -> list[dict]:
    signed = signed_query()
    return serialize_vectors() + reject_vectors() + [
        {
            "id": "message/sign/query-minimal",
            "section": "message",
            "requirement": ["core-model.md#2.1", "core-model.md#2.7", "crypto-suites.md#3"],
            "description": (
                "A complete query, signed under `eddsa-jws-2026`. The output is "
                "the compact serialization itself, which is what a `bytes` "
                "comparison is exact over — an object could not be compared that "
                "way, since the harness parses before comparing (P-001 §4.4)."
            ),
            "operation": "sign_query",
            "input": {"key_id": REQUESTER, "query": QUERY},
            "expect": {"outcome": "ok", "output": signed, "comparison": "bytes"},
        },
        {
            "id": "message/verify/query-valid",
            "section": "message",
            "requirement": ["core-model.md#4", "crypto-suites.md#3"],
            "description": (
                "Verification of that envelope reports the core object as it was "
                "signed. No `signature.value` is reattached from the third "
                "segment (crypto-suites.md §3): an implementation that added one "
                "would report an object no producer serialized."
            ),
            "operation": "verify_query",
            "input": {"envelope": {"signed": signed, "routing": ROUTING}},
            # `semantic`, not `bytes`: the output is a parsed object, and §4.4
            # reserves `bytes` for what the specification requires to be
            # byte-identical. The signed string above is that; its parse is not.
            "expect": {"outcome": "ok", "output": QUERY, "comparison": "semantic"},
        },
        {
            "id": "message/routing/subset",
            "section": "message",
            "requirement": ["core-model.md#2.1", "core-model.md#4"],
            "description": (
                "A routing projection carrying two of the six fields §2.1 permits "
                "rather than all six. §2.1 requires a strict subset of what "
                "`signed` contains and forbids introducing a field; it does not "
                "require any particular field, so an intermediary that needs only "
                "a predicate and an expiry projects only those. Step 8 compares "
                "what is present — `routing/disagrees` and "
                "`routing/introduces-field` are the two ways that comparison "
                "fails."
            ),
            "operation": "verify_query",
            "input": {
                "envelope": {
                    "signed": signed,
                    "routing": {
                        "predicate": {"id": QUERY["predicate"]["id"]},
                        "expires_at": QUERY["expires_at"],
                    },
                }
            },
            "expect": {"outcome": "ok", "output": QUERY, "comparison": "semantic"},
        },
        {
            "id": "message/verify/wrong-signer",
            "section": "message",
            "requirement": ["core-model.md#4", "core-model.md#5.2.1"],
            "description": (
                "A header naming `test-requester-1` over bytes signed by "
                "`test-requester-2`. The key resolves and the signature does not "
                "verify, so §4 step 4 rejects — and §5.2.1 gives one class for "
                "the whole of authentication, so this is indistinguishable from "
                "an unresolvable key, which is the point of collapsing them."
            ),
            "operation": "verify_query",
            "input": {
                "envelope": {"signed": signed_by_impostor(), "routing": ROUTING}
            },
            "expect": rejects("signature_invalid", "unauthenticated", 4),
        },
        {
            "id": "message/routing/disagrees",
            "section": "message",
            "requirement": ["core-model.md#2.1", "core-model.md#4",
                            "core-model.md#5.2.1"],
            "description": (
                "A routing projection whose `expires_at` differs from the "
                "verified object's by one second. §4 step 8 compares each "
                "projected field exactly, with no coercion, and §2.1 makes a "
                "disagreement a tampering signal rather than something to "
                "reconcile — so a difference this small still rejects."
            ),
            "operation": "verify_query",
            "input": {
                "envelope": {
                    "signed": signed,
                    "routing": dict(ROUTING, expires_at="2026-07-31T09:05:01Z"),
                }
            },
            "expect": rejects("routing_signed_mismatch", "routing_mismatch", 8),
        },
        {
            "id": "message/routing/introduces-field",
            "section": "message",
            "requirement": ["core-model.md#2.1", "core-model.md#4",
                            "core-model.md#5.2.1"],
            "description": (
                "A routing projection carrying `purpose`, which §2.1's list does "
                "not permit. The projected value is **byte-identical to the "
                "signed one**, so agreement is not what fails: §2.1 says "
                "`routing` carries at most six fields and that purpose is never "
                "projected, and a field outside that list is rejected however "
                "faithful its copy. A vector projecting a *differing* purpose "
                "would be rejected by the value comparison instead, and would "
                "not test this rule at all."
            ),
            "operation": "verify_query",
            "input": {
                "envelope": {
                    "signed": signed,
                    "routing": dict(ROUTING, purpose=QUERY["purpose"]),
                }
            },
            "expect": rejects("routing_introduced_field", "routing_mismatch", 8),
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
            print(f"differs from tools/author_message.py: {path.relative_to(REPO)}")
        for path in stale:
            print(f"not produced by tools/author_message.py: {path.relative_to(REPO)}")
        if differences or stale:
            print(
                f"\nFAILED: {len(differences) + len(stale)} file(s) out of step — "
                f"run `python3 tools/author_message.py`"
            )
            return 1
        print(f"{len(files)} vector(s) match tools/author_message.py")
        return 0

    for path in stale:
        path.unlink()
        print(f"removed (no longer authored): {path.relative_to(REPO)}")
    print(f"wrote {len(differences)} of {len(files)} vector(s) to "
          f"{SECTION.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
