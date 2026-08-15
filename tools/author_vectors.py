#!/usr/bin/env python3
"""Produce the bytes a corpus vector asserts, from the specification text.

    python3 tools/author_vectors.py --self-test

**Why this exists.** A `message/sign/` vector states the exact bytes a
conforming implementation produces. Whoever computes those bytes is
implementing the protocol — so if they come out of the Rust implementation,
running the corpus against Rust proves nothing (it is a change-detector for
Rust), and running it against Go proves Go matches *Rust*, with Rust's reading
of the specification silently promoted to truth. That inverts the argument the
project rests on: two implementations agreeing is evidence the specification is
unambiguous only if the thing they agree *against* did not come from one of
them.

So this reads the specification and produces the bytes independently of both.
Three readings instead of two, and a disagreement between this and either
implementation is a specification ambiguity found — which is what
[`mvp-scope.md`](../docs/mvp-scope.md) §7 says the project wants.

The pattern is not novel. RFC 8032 publishes test vectors computed from the
mathematical definition rather than dumped from a reference implementation, and
`conformance/keys/` already depends on that. Wycheproof authors crypto vectors
from specifications and attack classes rather than from any library, which is
why it found bugs in nearly every library. The opposite pattern — vectors
generated from the reference implementation — is how Protocol Buffers' language
ports diverged on wire-format edges for years, and it is why
[`crypto-suites.md`](../spec/crypto-suites.md) §3 declines to register a
JCS-based suite.

## Three disciplines, which are the decision and not decoration

1. **This is not "independent".** It has one author, the same as both
   implementations. Its independence is *structural* — a third language, written
   from the specification text, written before either implementation exists —
   and that is a real but bounded thing. It is never described as more.
2. **A disagreement between this tool and an implementation is a specification
   ambiguity under investigation, not an implementation bug**, until somebody
   shows which reading the specification text supports. Without that rule this
   quietly becomes the oracle, and the corpus is derived from an implementation
   again — just this one.
3. **This is not the harness.** It runs once per vector; its output is committed
   and thereafter treated as authored data. It is not imported by
   `conformance/harness/`, which is asserted by
   [`conformance/tests/test_dependencies.py`](../conformance/tests/test_dependencies.py).

## What it can produce today, and what it cannot

`serialize()` implements [P-002](../docs/prds/P-002-message-envelope.md) §4.2's
deterministic production profile, which is fully specified — nine rules, all
concrete.

`jws_compact()` assembles a signed string: header, payload, signature. The
header is [`crypto-suites.md`](../spec/crypto-suites.md) §3's — exactly `suite`
and `key_id`, no `alg` — which was an open question until it was raised as one
and decided in `spec/` rather than settled here.

That is the whole of what this file can produce today, and it is enough for a
`message/sign/` vector: the signed string is determined by the key, the key id,
and the object, so it is a byte-exact assertion rather than an approximate one.

## On the Ed25519 below

It is written from RFC 8032 §5.1's definition, and **the tool refuses to run
until it reproduces RFC 8032 §7.1's published test vectors**. That gating is
what makes it trustworthy rather than my arithmetic being trustworthy: every
constant here — the curve parameter, the group order, the base point — is
checked against three published known answers before anything is signed. A
mistake in any of them fails the self-test rather than producing a plausible
wrong vector.

Why not a library: none is installed, and CI has no install step. Adding one
would put the first third-party dependency in a repository that has none, for
code that runs once per vector. Stdlib-only means a reviewer reproduces the
corpus with `python3` and nothing else, which for a protocol project is the
point.

**This implementation is not constant-time and must never touch a real key.**
It signs with RFC 8032's published test seeds, which are public — there is no
secret here to leak, so the only property that matters is correctness, and that
is exactly what a known-answer test establishes. It is unsuitable for any other
purpose.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# crypto-suites.md §3's mandatory-to-implement suite, and the only one in 0.1.
SUITE = "eddsa-jws-2026"
KEY_FILE = REPO / "conformance" / "keys" / "ed25519-test-only.json"


# ---------------------------------------------------------------------------
# P-002 §4.2 — deterministic production profile
# ---------------------------------------------------------------------------

class ProfileError(Exception):
    """A value the production profile forbids. Never silently coerced."""


def json_type(value) -> str:
    """The JSON type, keeping the distinctions JSON keeps.

    `bool` before the number check: in Python `True == 1` and
    `isinstance(True, int)` are both true, and a serializer inheriting that
    would emit `1` for `true`.
    """
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, float):
        return "float"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    # Not a Python type name: `type(object()).__name__` is "object", which
    # collides with the JSON kind and had the serializer iterating a bare
    # object as though it were a mapping. A check must not crash on the input
    # it exists to reject.
    return "unsupported"


# core-model.md §2.2's timestamp, and RFC 3339 §5.6's grammar for the spellings
# it forbids. Written here from the specification text rather than imported
# from `conformance/harness/lint.py`, which reads the same section: two
# separate readings is the arrangement this tool exists for -- not independent
# ones, per the note at the top of this file -- and a
# disagreement between them is a specification ambiguity found.
# Fields core-model.md gives a timestamp: §2.2's `issued_at` and `expires_at`,
# §5.3's `expires_at`, §6's `decided_at`.
TIMESTAMP_FIELDS = frozenset({"issued_at", "expires_at", "decided_at"})

# `scope.md` §4.1's range, which is also what `src/value.rs` and `value.go`
# hold -- §4.1 chose it because it is the widest every conforming producer
# carries exactly. See the integer branch of `_serialize`.
INT64_MIN = -2**63
INT64_MAX = 2**63 - 1

# `[0-9]` rather than `\d`, which in Python matches every Unicode
# decimal digit -- Arabic-Indic, Devanagari, and about thirty others --
# and `int()` accepts them all. RFC 3339's grammar is `DIGIT`, which is
# ASCII, and both implementations compare bytes against `b'0'..=b'9'`.
# `strptime` used to refuse them and hid this; replacing it with
# arithmetic exposed it.
Q2D_TIMESTAMP = re.compile(
    r"\A([0-9]{4})-([0-9]{2})-([0-9]{2})T([0-9]{2}):([0-9]{2}):([0-9]{2})Z\Z")
RFC3339_ANY = re.compile(
    r"\A[0-9]{4}-[0-9]{2}-[0-9]{2}[Tt][0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+)?"
    r"([Zz]|[+-][0-9]{2}:[0-9]{2})\Z")


def days_in_month(year: int, month: int) -> int:
    """Gregorian, proleptic. Month 0 or 13 has no days, which the caller uses."""
    if month in (1, 3, 5, 7, 8, 10, 12):
        return 31
    if month in (4, 6, 9, 11):
        return 30
    if month == 2:
        leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
        return 29 if leap else 28
    return 0


def valid_q2d_timestamp(value: str) -> bool:
    """core-model.md §2.2's timestamp: the one spelling, and a real instant.

    Shape *and* meaning. `2026-99-99T99:99:99Z` has §2.2's spelling exactly and
    is no date, so a check on the spelling alone would sign it into a payload
    that nothing downstream can read as text. RFC 3339's own grammar requires
    this much -- its `date-mday` says the maximum "varies based on the month and
    year" -- so it is §2.2's rule rather than an addition to it.

    Arithmetic rather than `datetime`, which cannot represent a year below 1 and
    would therefore refuse `0000-01-01T00:00:00Z`. RFC 3339's `date-fullyear` is
    four digits and admits it, §2.2 adds a spelling and no floor, and the two
    implementations do their own arithmetic and accept it. A library's range is
    not a specification's, and the tool that authors the corpus must not be the
    narrowest reader in the room.
    """
    matched = Q2D_TIMESTAMP.match(value)
    if not matched:
        return False
    year, month, day, hour, minute, second = (int(g) for g in matched.groups())
    if second == 60:
        # RFC 3339 §5.7: 23:59 at a month end. Which leap seconds were actually
        # inserted is IERS data and not statically decidable -- see the harness,
        # which reaches the same conclusion from the same section.
        if (hour, minute) != (23, 59) or day != days_in_month(year, month):
            return False
        second = 59
    return (1 <= month <= 12 and 1 <= day <= days_in_month(year, month)
            and hour <= 23 and minute <= 59 and second <= 59)


def encodable(value: str, what: str) -> None:
    """Refuse a `str` Python can hold and the profile cannot emit.

    §4.2 produces UTF-8. A Python `str` is a sequence of code points and may
    contain an unpaired surrogate, which has no UTF-8 encoding at all.

    Go and Rust refuse the same value -- Go because a string carrying invalid
    UTF-8 would otherwise be silently substituted with U+FFFD, Rust because its
    `String` cannot hold one in the first place. Without this the three
    implementations would differ on which values *exist* rather than on what
    they produce, and the error would arrive as an encoding failure from
    somewhere inside the profile rather than as the profile refusing it.

    The message names what was being encoded and nothing else -- not the
    character, and not the position either: where a string first goes wrong is
    a fact about the string, and this serializer runs over responses and
    receipts whose strings come from data the requester never sees.
    """
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        raise ProfileError(
            f"{what} is not encodable as UTF-8. P-002 §4.2 produces UTF-8, and "
            f"an unpaired surrogate has no encoding in it") from None


def sort_key(key: str) -> bytes:
    """§4.2: object keys sorted ascending by **UTF-16 code unit**.

    Not Python's default, which orders by Unicode code point. The two disagree
    above the BMP: U+1F680 encodes as the surrogate pair D83D DE80, which sorts
    *below* U+E000, while by code point it sorts above. Comparing the UTF-16BE
    encoding as bytes is the same ordering as comparing code-unit sequences,
    and is the rule JCS states and P-002 §4.2 borrows as an ordering convention.

    This is the single subtlest line in the profile, and the one two
    implementations are most likely to disagree about while both looking right.
    """
    return key.encode("utf-16-be")


def escape_string(value: str) -> str:
    """§4.2: minimal escaping; no `\\uXXXX` for characters representable directly.

    JSON requires escaping exactly three things: the quote, the backslash, and
    control characters below U+0020. Everything else is emitted as itself --
    including `/`, which JSON permits escaping and this profile does not.

    A control character is not "representable directly" (JSON forbids a raw one
    inside a string), so it must be escaped, and *minimal* selects the two-character
    short form where RFC 8259 defines one.
    """
    out = ['"']
    short = {'"': '\\"', "\\": "\\\\", "\b": "\\b", "\f": "\\f",
             "\n": "\\n", "\r": "\\r", "\t": "\\t"}
    for char in value:
        if char in short:
            out.append(short[char])
        elif ord(char) < 0x20:
            out.append(f"\\u{ord(char):04x}")
        else:
            out.append(char)
    out.append('"')
    return "".join(out)


# Where core-model.md gives those names a timestamp's meaning: the top level of
# the object being serialized -- a core object (§2.2) or a response (§5.3) --
# and the `receipt` inside it (§6). Nowhere else: `public_context` and a
# predicate's own structures are operation-defined, and a field called
# `expires_at` in one is its entry's to shape.
# `routing` is here as well as `receipt`, because §2.2 covers "the core object,
# `routing`, and a receipt" -- and `routing` is where the spelling matters most,
# since §4 step 8 compares its fields against the verified object's.
PROTOCOL_SUBOBJECTS = frozenset({"receipt", "routing"})


def serialize(value) -> bytes:
    """A protocol structure as P-002 §4.2's profile produces it. UTF-8, no BOM.

    A core object, a response, a receipt, or `routing`. For a predicate's own
    data use `serialize_operation_data`: the bytes are the same and the
    field-name rules are not.

    Returns bytes rather than a string, because the profile is about bytes and
    a caller that wants to sign them must not have to guess an encoding.
    """
    return _serialize(value, protocol_level=True).encode("utf-8")


def serialize_operation_data(value) -> bytes:
    """Operation-defined data under the same profile.

    Identical bytes, and one difference in what is refused: §2.4 says a
    predicate's `public_context` is its entry's to shape, so a field there
    called `issued_at` is the predicate's and not §2.2's.

    Two entry points rather than one, because protocol level is a property of
    *what the caller is serializing* and cannot be read off the nesting.
    Reached through a query, `public_context` is already below protocol level;
    digested on its own for P-002 §4.7's `public_context_digest` it would be the
    root, and a single entry point would hold the same bytes to two different
    rules depending on how they were reached.
    """
    return _serialize(value, protocol_level=False).encode("utf-8")


def _serialize(value, protocol_level: bool = False) -> str:
    kind = json_type(value)

    if kind == "float":
        # §4.3: "The serializer enforces this: a float reaching it is a
        # programming error and fails loudly rather than emitting a value two
        # implementations might render differently."
        raise ProfileError(
            f"float {value!r} in a signed structure — prohibited by P-002 §4.3. "
            f"Capacity is integer millibits, timestamps are strings, sizes and "
            f"cardinalities are integers. Adding a float field is an escalation")

    if kind == "null":
        return "null"
    if kind == "boolean":
        return "true" if value else "false"
    if kind == "integer":
        # §4.2: no exponent, no leading `+`, no leading zeros. Python's int
        # repr is exactly that, for every magnitude -- there is no 2^53 cliff
        # here, which is one of the hazards crypto-suites.md §3 cites against
        # a JCS-based suite.
        #
        # Bounded to the range `scope.md` §4.1 requires an entry's integers to
        # lie within, which is also what both value models hold. Python cannot
        # otherwise be stopped from exceeding it: `int` is arbitrary-precision.
        # Without this the tool could author a vector neither implementation can
        # reproduce, and the first sign would be a byte disagreement blamed on
        # the implementations. E-37, closed as B.
        #
        # `core-model.md` still states no range, deliberately: every integer the
        # protocol itself defines is a count, a cardinality, or a capacity in
        # integer millibits, none of which approaches 2**63. The bound is about
        # registry data, and a vector carrying `public_context` is registry data
        # in a corpus file.
        if not INT64_MIN <= value <= INT64_MAX:
            raise ProfileError(
                f"integer is outside −2^63 … 2^63 − 1, which scope.md §4.1 "
                f"requires an entry's integers to lie within and both value "
                f"models hold. The tool does not author what the pair cannot "
                f"serialize")
        return str(value)
    if kind == "string":
        encodable(value, "string")
        # A string is written as it is. §2.2 states its spelling for the fields
        # it names -- and since E-36 closed as C, says so explicitly: "the rule
        # reaches the fields this specification names, and no further". A string
        # elsewhere is operation-defined data under §2.4, and whether it has one
        # spelling is the predicate's entry to say, through `scope.md` §4.1's
        # `format: date-time`.
        return escape_string(value)
    if kind == "array":
        return "[" + ",".join(_serialize(item) for item in value) + "]"
    if kind == "object":
        for key in value:
            if not isinstance(key, str):
                raise ProfileError(f"object key {key!r} is not a string")
            # Before sorting, not during: `sort_key` encodes to UTF-16BE and
            # would raise a `UnicodeEncodeError` from inside the comparison --
            # a refusal, but not one that names what was wrong or comes from
            # the profile. The other two implementations refuse the same value.
            encodable(key, "object key")
        # Duplicate keys cannot occur in a Python dict, so §4.2's production
        # rule is structurally satisfied. Parsing is where it has to be
        # enforced, and conformance/harness/corpus.py does that.
        keys = sorted(value, key=sort_key)
        for key in keys:
            # By name as well as by shape: core-model.md gives these fields
            # timestamps, so a malformed one is caught however malformed --
            # `2026-1-01T00:00:00Z` has no RFC 3339 shape and is still a
            # timestamp field. §2.2, §5.3 and §6 name them, so this is a
            # citation rather than a guess.
            if protocol_level and key in TIMESTAMP_FIELDS:
                if not isinstance(value[key], str):
                    raise ProfileError(
                        f"{key} is a timestamp field and holds a "
                        f"{type(value[key]).__name__} rather than a string. "
                        f"core-model.md §2.2's timestamp is one")
                if not valid_q2d_timestamp(value[key]):
                    # The value is not in the message. This serializer runs over
                    # responses and receipts too, whose strings derive from data
                    # the requester never sees, and an error is a place one of
                    # them could reach a log.
                    raise ProfileError(
                        f"{key} is a timestamp field and its value is not "
                        f"core-model.md §2.2's timestamp — uppercase `T`, "
                        f"uppercase `Z`, second precision, and a real instant")
        # `receipt` re-enters protocol level only from protocol level. A
        # `public_context` carrying a field called `receipt` is the predicate's
        # own structure, and promoting it would enforce §6's field meanings
        # inside data the previous line leaves to a predicate's entry.
        return "{" + ",".join(
            f"{escape_string(k)}:"
            f"{_serialize(value[k], protocol_level=protocol_level and k in PROTOCOL_SUBOBJECTS)}"
            for k in keys) + "}"

    raise ProfileError(
        f"{type(value).__name__} is not a JSON value: {value!r}. The profile "
        f"produces JSON, so every value must already be one")


# ---------------------------------------------------------------------------
# Ed25519, from RFC 8032 §5.1 — gated on §7.1's published known answers
# ---------------------------------------------------------------------------

P = 2**255 - 19
L = 2**252 + 27742317777372353535851937790883648493
D = (-121665 * pow(121666, P - 2, P)) % P

# RFC 8032 §5.1's base point. Not trusted from memory: if either coordinate is
# wrong, TEST 1's public key does not match and the self-test refuses to let
# the tool run.
BASE_X = 15112221349535400772501151409588531511454012693041857206046113283949847762202
BASE_Y = 46316835694926478169428394003475163141307993866256225615783033603165251855960


def _add(p1, p2):
    """Extended twisted-Edwards addition, a = -1 (RFC 8032 §5.1.4)."""
    x1, y1, z1, t1 = p1
    x2, y2, z2, t2 = p2
    a = ((y1 - x1) * (y2 - x2)) % P
    b = ((y1 + x1) * (y2 + x2)) % P
    c = (2 * t1 * D * t2) % P
    d = (2 * z1 * z2) % P
    e, f, g, h = b - a, d - c, d + c, b + a
    return ((e * f) % P, (g * h) % P, (f * g) % P, (e * h) % P)


def _scalar_mult(point, scalar):
    result = (0, 1, 1, 0)          # the neutral element
    while scalar > 0:
        if scalar & 1:
            result = _add(result, point)
        point = _add(point, point)
        scalar >>= 1
    return result


def _encode_point(point) -> bytes:
    """y as 255-bit little-endian, with the top bit carrying x's parity."""
    x, y, z, _ = point
    inv_z = pow(z, P - 2, P)
    x, y = (x * inv_z) % P, (y * inv_z) % P
    return ((y | ((x & 1) << 255)).to_bytes(32, "little"))


def _clamp(h: bytes) -> int:
    """RFC 8032 §5.1.5 step 1: prune the buffer."""
    a = bytearray(h[:32])
    a[0] &= 0xF8
    a[31] &= 0x7F
    a[31] |= 0x40
    return int.from_bytes(a, "little")


BASE = (BASE_X, BASE_Y, 1, (BASE_X * BASE_Y) % P)


def public_key(seed: bytes) -> bytes:
    """RFC 8032 §5.1.5. `seed` is the 32-byte secret key."""
    if len(seed) != 32:
        raise ValueError(f"seed must be 32 bytes, got {len(seed)}")
    return _encode_point(_scalar_mult(BASE, _clamp(hashlib.sha512(seed).digest())))


def sign(seed: bytes, message: bytes) -> bytes:
    """RFC 8032 §5.1.6. Deterministic: no randomness, by construction.

    That determinism is what makes cross-implementation comparison a byte
    comparison rather than a both-verify check (P-001 §4.8), and it is why the
    same seed and message here produce the same 64 bytes anywhere.
    """
    if len(seed) != 32:
        raise ValueError(f"seed must be 32 bytes, got {len(seed)}")
    h = hashlib.sha512(seed).digest()
    a = _clamp(h)
    prefix = h[32:]
    encoded_a = _encode_point(_scalar_mult(BASE, a))

    r = int.from_bytes(hashlib.sha512(prefix + message).digest(), "little") % L
    encoded_r = _encode_point(_scalar_mult(BASE, r))

    k = int.from_bytes(
        hashlib.sha512(encoded_r + encoded_a + message).digest(), "little") % L
    s = (r + k * a) % L
    return encoded_r + s.to_bytes(32, "little")


# ---------------------------------------------------------------------------
# The gate
# ---------------------------------------------------------------------------

class KnownAnswerFailure(Exception):
    """The Ed25519 above does not reproduce RFC 8032. Nothing may be authored."""


def known_answers() -> list[dict]:
    document = json.loads(KEY_FILE.read_text(encoding="utf-8"))
    keys = document["keys"]
    return [{**answer, "seed": keys[answer["key"]]["seed"],
             "public_key": keys[answer["key"]]["public_key"]}
            for answer in document["known_answers"]]


def check_known_answers() -> None:
    """Reproduce RFC 8032 §7.1, or refuse to author anything.

    Fail-closed, and the reason is the same one the protocol applies to itself:
    a signer that cannot be shown correct must not produce something that will
    be treated as correct. A vector authored by a broken signer is worse than
    no vector, because it becomes the answer two implementations are held to.
    """
    answers = known_answers()
    if len(answers) < 3:
        raise KnownAnswerFailure(
            f"only {len(answers)} known answers available; the gate would be "
            f"weaker than the RFC it cites")

    for answer in answers:
        seed = bytes.fromhex(answer["seed"])
        message = bytes.fromhex(answer["message"])

        derived = public_key(seed).hex()
        if derived != answer["public_key"]:
            raise KnownAnswerFailure(
                f"{answer['source']}: derived public key {derived}, "
                f"RFC 8032 publishes {answer['public_key']}")

        produced = sign(seed, message).hex()
        if produced != answer["signature"]:
            raise KnownAnswerFailure(
                f"{answer['source']}: produced signature {produced}, "
                f"RFC 8032 publishes {answer['signature']}")


def base64url(raw: bytes) -> str:
    """RFC 7515's base64url: no padding, URL-safe alphabet."""
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def jws_compact(seed: bytes, key_id: str, payload, suite: str = SUITE) -> str:
    """The `signed` string: header, payload, signature, dot-separated.

    P-003 §4.1:

        signed        = BASE64URL(protected_header) "." BASE64URL(payload)
                        "." BASE64URL(signature)
        signing_input = ASCII(BASE64URL(protected_header) "."
                        BASE64URL(payload))

    The header is `crypto-suites.md` §3's: exactly `suite` and `key_id`, in the
    order P-002 §4.2's key rule fixes, which is `key_id` first. No `alg` --
    §3 is explicit that a Q2D header does not carry one, so that a JOSE library
    cannot select a verification algorithm from data nobody has authenticated
    yet.

    `payload` is serialized by the same profile, so the whole signed string is
    determined by the key, the key id, and the object -- which is what makes a
    `message/sign/` vector a byte-exact assertion rather than an approximate
    one.
    """
    return jws_with_header(seed, {"key_id": key_id, "suite": suite}, payload)


def jws_with_header(seed: bytes, header, payload) -> str:
    """The same construction, over a header supplied whole.

    `jws_compact` is the conforming producer. This is what a `suite/` vector
    needs to express a **non**-conforming one: a header carrying `alg`, or
    declaring a suite the payload does not, is a message no correct
    implementation emits and every correct implementation must reject
    ([P-003](../docs/prds/P-003-crypto-suites.md) §6). Producing it is the only
    way to assert the rejection.

    The signature is over whatever header is given, so these are validly signed
    messages that are wrong in exactly one stated way -- not corrupt bytes,
    which would fail for a reason the vector is not about.
    """
    check_known_answers()

    signing_input = f"{base64url(serialize(header))}.{base64url(serialize(payload))}"
    signature = sign(seed, signing_input.encode("ascii"))
    return f"{signing_input}.{base64url(signature)}"


def main(argv: list[str]) -> int:
    if "--self-test" not in argv[1:]:
        print(__doc__.strip().splitlines()[0])
        print("\nusage: python3 tools/author_vectors.py --self-test")
        return 2

    check_known_answers()
    print(f"Ed25519 reproduces all {len(known_answers())} RFC 8032 §7.1 vectors")

    # Signing something end to end, so the self-test covers the thing the tool
    # is for rather than only the primitive underneath it.
    keys = json.loads(KEY_FILE.read_text(encoding="utf-8"))["keys"]
    key_id, key = next(iter(keys.items()))
    signed = jws_compact(bytes.fromhex(key["seed"]), key_id, {"type": "query"})
    print(f"P-002 §4.2 serializer and crypto-suites.md §3 header available")
    print(f"\n  {signed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
