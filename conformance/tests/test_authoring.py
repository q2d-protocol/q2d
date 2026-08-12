"""The vector-authoring tool produces what the specification says (P-001 §10).

    python3 -m unittest discover -s conformance/tests

[`tools/author_vectors.py`](../../tools/author_vectors.py) exists so the corpus
is not derived from an implementation it is supposed to check. That only holds
while the tool actually implements the specification, so this is where each of
[P-002](../../docs/prds/P-002-message-envelope.md) §4.2's rules gets a test,
and where RFC 8032's known answers gate the signer.

**The known-answer gate is the load-bearing test in this file.** Every constant
in the Ed25519 — the curve parameter, the group order, the base point — is
checked against three vectors published by the IETF. A mistake in any of them
fails here rather than producing a plausible wrong signature that becomes the
answer two implementations are held to.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))

import author_vectors as author  # noqa: E402


class KnownAnswerTest(unittest.TestCase):
    def test_ed25519_reproduces_rfc_8032(self):
        # Raises KnownAnswerFailure naming the vector if it does not.
        author.check_known_answers()

    def test_all_three_published_vectors_are_exercised(self):
        # The gate is only as strong as what it checks. RFC 8032 §7.1 TESTs 1-3
        # cover the empty message, one byte, and two bytes; a gate that had
        # quietly dropped to one would still pass the test above.
        answers = author.known_answers()
        self.assertEqual(len(answers), 3)
        self.assertEqual({len(bytes.fromhex(a["message"])) for a in answers},
                         {0, 1, 2})

    def test_signing_is_deterministic(self):
        # RFC 8032 signing takes no randomness. This is what makes P-001 §4.8's
        # cross-implementation assertion a byte comparison rather than a
        # both-verify check, so it is worth asserting rather than assuming.
        seed = bytes.fromhex(author.known_answers()[0]["seed"])
        self.assertEqual(author.sign(seed, b"q2d"), author.sign(seed, b"q2d"))

    def test_a_one_bit_message_change_changes_the_signature(self):
        seed = bytes.fromhex(author.known_answers()[0]["seed"])
        self.assertNotEqual(author.sign(seed, b"\x00"), author.sign(seed, b"\x01"))

    def test_a_seed_of_the_wrong_length_is_refused(self):
        for length in (0, 31, 33, 64):
            with self.subTest(length=length):
                with self.assertRaises(ValueError):
                    author.sign(b"\x00" * length, b"")


class KeyOrderTest(unittest.TestCase):
    """§4.2: object keys sorted ascending by UTF-16 code unit."""

    def test_ascii_keys_sort_ascending(self):
        self.assertEqual(author.serialize({"b": 1, "a": 2, "c": 3}),
                         b'{"a":2,"b":1,"c":3}')

    def test_utf16_order_is_not_code_point_order(self):
        # The rule's whole content is in this case, and it is the one two
        # implementations are most likely to disagree about while both look
        # right. U+1F680 encodes as the surrogate pair D83D DE80, so by UTF-16
        # code unit it sorts *below* U+E000; by Unicode code point it sorts
        # above. Python's default sort is by code point.
        rocket, private_use = "\U0001F680", ""
        self.assertLess(private_use, rocket, "Python sorts by code point")

        serialized = author.serialize({rocket: 1, private_use: 2}).decode("utf-8")
        self.assertLess(serialized.index(rocket), serialized.index(private_use),
                        "keys must sort by UTF-16 code unit, not code point")

    def test_nested_objects_are_sorted_too(self):
        self.assertEqual(author.serialize({"z": {"b": 1, "a": 2}}),
                         b'{"z":{"a":2,"b":1}}')

    def test_array_order_is_preserved(self):
        # Arrays are ordered data, not a set. §4.4 makes array order
        # significant for comparison, and sorting one here would destroy the
        # thing being compared.
        self.assertEqual(author.serialize([3, 1, 2]), b"[3,1,2]")


class NumberTest(unittest.TestCase):
    def test_a_float_is_refused_loudly(self):
        # §4.3: "a float reaching it is a programming error and fails loudly
        # rather than emitting a value two implementations might render
        # differently".
        for value in (1.0, 0.1, {"a": 1.5}, [2.5]):
            with self.subTest(value=value):
                with self.assertRaises(author.ProfileError):
                    author.serialize(value)

    def test_a_large_integer_survives_exactly(self):
        # crypto-suites.md §3 cites JCS inheriting ECMAScript number semantics
        # -- integers above 2^53 not round-tripping -- as a reason not to
        # register a canonicalization suite. This profile has no such cliff.
        big = 2**53 + 1
        self.assertEqual(author.serialize({"n": big}),
                         f'{{"n":{big}}}'.encode("utf-8"))
        self.assertEqual(author.serialize(2**64), str(2**64).encode("utf-8"))

    def test_integers_carry_no_exponent_or_leading_zero(self):
        self.assertEqual(author.serialize(0), b"0")
        self.assertEqual(author.serialize(-7), b"-7")
        self.assertEqual(author.serialize(10**21), str(10**21).encode("utf-8"))

    def test_a_boolean_is_not_a_number(self):
        # In Python `True == 1` and `isinstance(True, int)`. A serializer that
        # inherited that would emit 1 where the vector says true.
        self.assertEqual(author.serialize(True), b"true")
        self.assertEqual(author.serialize({"a": False}), b'{"a":false}')


class StringTest(unittest.TestCase):
    """§4.2: minimal escaping; no `\\uXXXX` for characters representable directly."""

    def test_non_ascii_is_emitted_directly(self):
        self.assertEqual(author.serialize("café"), '"café"'.encode("utf-8"))
        self.assertEqual(author.serialize("日本"), '"日本"'.encode("utf-8"))

    def test_a_solidus_is_not_escaped(self):
        # JSON permits escaping `/` and this profile does not, because escaping
        # it is not minimal.
        self.assertEqual(author.serialize("a/b"), b'"a/b"')

    def test_the_two_required_escapes(self):
        self.assertEqual(author.serialize('a"b'), b'"a\\"b"')
        self.assertEqual(author.serialize("a\\b"), b'"a\\\\b"')

    def test_control_characters_take_the_short_form(self):
        # A control character is not "representable directly" -- JSON forbids a
        # raw one in a string -- so it must be escaped, and minimal selects the
        # two-character form where RFC 8259 defines one.
        self.assertEqual(author.serialize("a\nb"), b'"a\\nb"')
        self.assertEqual(author.serialize("\t"), b'"\\t"')
        self.assertEqual(author.serialize("\r"), b'"\\r"')

    def test_a_control_character_with_no_short_form_uses_lowercase_hex(self):
        self.assertEqual(author.serialize("\x00"), b'"\\u0000"')
        self.assertEqual(author.serialize("\x1f"), b'"\\u001f"')

    def test_delete_is_not_a_control_character_for_json(self):
        # U+007F is representable directly and RFC 8259 does not require
        # escaping it, so minimal escaping leaves it alone.
        self.assertEqual(author.serialize("\x7f"), '"\x7f"'.encode("utf-8"))


class ProfileShapeTest(unittest.TestCase):
    def test_output_is_bytes_with_no_bom(self):
        # §4.2: UTF-8, no BOM. Returned as bytes because the profile is about
        # bytes, and a caller that signs them must not have to guess.
        out = author.serialize({"a": "é"})
        self.assertIsInstance(out, bytes)
        self.assertFalse(out.startswith(b"\xef\xbb\xbf"))

    def test_no_whitespace_between_tokens(self):
        out = author.serialize({"a": [1, 2], "b": {"c": 3}})
        self.assertEqual(out, b'{"a":[1,2],"b":{"c":3}}')
        self.assertNotIn(b" ", out)

    def test_null_serializes_rather_than_being_refused(self):
        # §4.2 says an absent optional field is *omitted, never null* -- a rule
        # binding whoever builds the object, not the serializer. `null` is a
        # legitimate value: the registry's `none-free-returns-null` vector
        # answers exactly that.
        self.assertEqual(author.serialize(None), b"null")
        self.assertEqual(author.serialize({"result": None}), b'{"result":null}')

    def test_a_non_string_key_is_refused(self):
        with self.assertRaises(author.ProfileError):
            author.serialize({1: "a"})

    def test_an_unserializable_value_is_refused(self):
        for value in (set(), object(), b"bytes"):
            with self.subTest(value=type(value).__name__):
                with self.assertRaises(author.ProfileError):
                    author.serialize(value)


class BlockedTest(unittest.TestCase):
    def test_jws_assembly_refuses_rather_than_guessing(self):
        # The protected header's member set is unspecified. A guess here would
        # resolve a specification ambiguity in a generator, and every signed
        # vector in the corpus would then assert it.
        with self.assertRaises(NotImplementedError) as raised:
            author.jws_compact()
        self.assertIn("protected header", str(raised.exception))

    def test_running_without_self_test_explains_the_block(self):
        self.assertEqual(author.main(["author_vectors.py"]), 2)


if __name__ == "__main__":
    unittest.main()
