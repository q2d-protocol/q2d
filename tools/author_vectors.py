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

The Ed25519 below signs. The JWS compact serialization does **not** assemble,
because the protected header's member set is not specified anywhere: P-003 §4.1
gives the structure, §4.2 says a verifier reads "the declared suite" from the
header, and `crypto-suites.md` implies `alg` exists by rejecting `alg: none` —
but no document says whether the header is `{"alg": "EdDSA", "kid": …}` or
`{"suite": "eddsa-jws-2026", "kid": …}` or both. §4.2's sorting rule determines
the *order* once the members are known, so this is the one remaining gap between
the specification and a byte-exact signed vector. It is P-001 §10, raised rather
than decided: choosing here would resolve a specification ambiguity in a
generator, which is the thing CLAUDE.md is most explicit about not doing.

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

import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
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


def serialize(value) -> bytes:
    """A value as P-002 §4.2's profile produces it. UTF-8, no BOM.

    Returns bytes rather than a string, because the profile is about bytes and
    a caller that wants to sign them must not have to guess an encoding.
    """
    return _serialize(value).encode("utf-8")


def _serialize(value) -> str:
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
        return str(value)
    if kind == "string":
        return escape_string(value)
    if kind == "array":
        return "[" + ",".join(_serialize(item) for item in value) + "]"
    if kind == "object":
        for key in value:
            if not isinstance(key, str):
                raise ProfileError(f"object key {key!r} is not a string")
        # Duplicate keys cannot occur in a Python dict, so §4.2's production
        # rule is structurally satisfied. Parsing is where it has to be
        # enforced, and conformance/harness/corpus.py does that.
        keys = sorted(value, key=sort_key)
        return "{" + ",".join(f"{escape_string(k)}:{_serialize(value[k])}"
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


def jws_compact(*_args, **_kwargs):
    """Not implementable yet — the protected header's members are unspecified.

    P-003 §4.1 gives the structure and §4.2 says a verifier reads the declared
    suite from the header, but no document in this repository says which members
    the header carries. P-002 §4.2's sorting rule fixes their order once they
    are known, so this is the one thing between a specified profile and a
    byte-exact signed vector.

    Raising rather than guessing: a guess here would be a specification
    ambiguity resolved in a generator, and every signed vector in the corpus
    would then assert it.
    """
    raise NotImplementedError(
        "the JWS protected header's member set is not specified — see P-001 §10 "
        "and P-003 §4.1. Authoring a signed vector needs that decision first")


def main(argv: list[str]) -> int:
    if "--self-test" not in argv[1:]:
        print(__doc__.strip().splitlines()[0])
        print("\nusage: python3 tools/author_vectors.py --self-test")
        print("\nSigned vectors cannot be authored yet: the JWS protected "
              "header's\nmember set is unspecified. See P-001 §10.")
        return 2

    check_known_answers()
    print(f"Ed25519 reproduces all {len(known_answers())} RFC 8032 §7.1 vectors")
    print(f"P-002 §4.2 serializer available; JWS assembly blocked on P-001 §10")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
