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

import base64
import json
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
        # Up to the range the two implementations hold, exactly -- E-37.
        self.assertEqual(author.serialize(2**63 - 1), str(2**63 - 1).encode("utf-8"))

    def test_an_integer_beyond_the_pair_s_range_is_refused_not_rounded(self):
        # E-37's bound, and it is not the cliff the test above is about. JCS
        # inherits a *silent* loss above 2^53: the value round-trips to a
        # different number and nothing says so. This refuses, which is the
        # opposite failure -- no vector is authored at all, so none can assert
        # bytes an implementation cannot produce.
        with self.assertRaises(author.ProfileError):
            author.serialize(2**63)
        with self.assertRaises(author.ProfileError):
            author.serialize(-2**63 - 1)

    def test_integers_carry_no_exponent_or_leading_zero(self):
        self.assertEqual(author.serialize(0), b"0")
        self.assertEqual(author.serialize(-7), b"-7")
        # 10**21 would be rendered in exponent form by a naive float path and
        # is above E-37's bound, so the assertion that carries the point is the
        # largest value the profile admits -- twenty digits, no exponent.
        self.assertEqual(author.serialize(2**63 - 1), b"9223372036854775807")

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


class JwsTest(unittest.TestCase):
    """crypto-suites.md §3's protected header, and the signed string over it."""

    def setUp(self):
        key = author.known_answers()[0]
        self.seed = bytes.fromhex(key["seed"])
        self.key_id = key["key"]

    def signed(self, payload=None):
        return author.jws_compact(self.seed, self.key_id,
                                  {"type": "query"} if payload is None else payload)

    def test_the_header_carries_exactly_suite_and_key_id(self):
        header = self.signed().split(".")[0]
        decoded = json.loads(base64.urlsafe_b64decode(header + "=="))
        self.assertEqual(set(decoded), {"suite", "key_id"})
        self.assertEqual(decoded["suite"], author.SUITE)
        self.assertEqual(decoded["key_id"], self.key_id)

    def test_the_header_carries_no_alg(self):
        # §3: a header a general-purpose JOSE library can process is one where
        # that library selects the verification algorithm from data nobody has
        # authenticated yet. `alg: none` is not a state this format can express.
        header = base64.urlsafe_b64decode(self.signed().split(".")[0] + "==")
        self.assertNotIn(b"alg", header)

    def test_the_header_members_are_in_the_profile_s_order(self):
        # P-002 §4.2 sorts keys ascending by UTF-16 code unit, so `key_id`
        # precedes `suite`. Two implementations disagreeing here produce
        # different bytes for the same message.
        header = base64.urlsafe_b64decode(self.signed().split(".")[0] + "==")
        self.assertLess(header.index(b"key_id"), header.index(b"suite"))

    def test_the_signed_string_has_three_parts_and_no_padding(self):
        parts = self.signed().split(".")
        self.assertEqual(len(parts), 3)
        for part in parts:
            self.assertNotIn("=", part)
            self.assertNotIn("+", part)
            self.assertNotIn("/", part)

    def test_signing_is_deterministic_end_to_end(self):
        # What makes a message/sign/ vector a byte-exact assertion.
        self.assertEqual(self.signed(), self.signed())

    def test_the_signature_covers_the_header_and_payload(self):
        # RFC 7515's signing input, so a changed header changes the signature
        # even when the payload is identical.
        other = author.jws_compact(self.seed, "test-custodian-1",
                                   {"type": "query"})
        self.assertNotEqual(self.signed().split(".")[2], other.split(".")[2])

    def test_a_timestamp_in_the_wrong_spelling_is_refused(self):
        # The last point a value can be rejected before it becomes bytes
        # somebody signs. Inside a signed payload it is past the reach of
        # anything that reads the vector as text — `harness lint` walks the
        # vector's strings, and a compact serialization is one opaque string
        # to it.
        for wrong in ("2026-01-01t00:00:00z", "2026-01-01T00:00:00+00:00",
                      "2026-01-01T00:00:00.5Z"):
            with self.subTest(value=wrong):
                with self.assertRaises(author.ProfileError):
                    self.signed({"issued_at": wrong})

    def test_a_right_shaped_non_instant_is_refused(self):
        # §2.2's spelling exactly, and no date. Checking the spelling alone
        # would have signed it into a payload nothing downstream reads as text.
        for wrong in ("2026-99-99T99:99:99Z", "2026-02-30T00:00:00Z",
                      "2026-01-01T00:00:60Z"):
            with self.subTest(value=wrong):
                with self.assertRaises(author.ProfileError):
                    self.signed({"issued_at": wrong})

    def test_year_zero_is_accepted_because_rfc_3339_admits_it(self):
        # This tool used `datetime.strptime`, which starts at year 1, and so
        # refused a spelling both implementations accept. §2.2 adds a spelling
        # to RFC 3339 and says nothing about a range, and `date-fullyear` is
        # four digits -- so the refusal was a library's range standing in for a
        # specification's. It validates arithmetically now.
        #
        # Year zero is absurd and this is not where that is caught: §4 step 6
        # compares `expires_at` against a clock, and no year-zero query
        # survives it.
        for low in ("0000-01-01T00:00:00Z", "0001-01-01T00:00:00Z"):
            with self.subTest(value=low):
                self.assertTrue(author.valid_q2d_timestamp(low))

    def test_empty_objects_and_arrays_serialize(self):
        # A `query` is legitimately empty in the minimal message vector, and a
        # serializer that crashed on one could author no signed vector at all.
        self.assertEqual(author.serialize({}), b"{}")
        self.assertEqual(author.serialize([]), b"[]")
        self.assertEqual(author.serialize({"query": {}}), b'{"query":{}}')

    def test_a_named_timestamp_field_is_checked_however_malformed(self):
        with self.assertRaises(author.ProfileError):
            self.signed({"issued_at": "2026-1-01T00:00:00Z"})
        with self.assertRaises(author.ProfileError):
            self.signed({"expires_at": "soon"})

    def test_a_timestamp_field_holding_a_number_is_refused(self):
        # The JWT/DNSSEC representation, in a protocol that chose strings.
        # Signing it would put protocol metadata into covered bytes that
        # conforming implementations reject.
        for value in (1767225600, None, [], {"seconds": 0}):
            with self.subTest(value=value):
                with self.assertRaises(author.ProfileError):
                    self.signed({"issued_at": value})

    def test_the_name_rule_does_not_reach_operation_defined_objects(self):
        # core-model.md gives those names a timestamp's meaning at the top
        # level of a core object or response, and inside `receipt`. A
        # `public_context` field called `expires_at` is the predicate's, and
        # may mean anything.
        author.serialize({"public_context": {"expires_at": "never"}})
        with self.assertRaises(author.ProfileError):
            author.serialize({"receipt": {"decided_at": "never"}})
        with self.assertRaises(author.ProfileError):
            author.serialize({"issued_at": "never"})

    def test_a_predicate_may_have_its_own_receipt(self):
        # `receipt` re-enters protocol level only from protocol level. A
        # predicate's own structure called `receipt` is not §6's.
        author.serialize({"public_context": {"receipt": {"decided_at": "never"}}})
        with self.assertRaises(author.ProfileError):
            author.serialize({"receipt": {"decided_at": "never"}})

    def test_routing_timestamps_are_checked(self):
        # §2.2 covers "the core object, `routing`, and a receipt", and routing
        # is where the spelling matters most: §4 step 8 compares its fields
        # against the verified object's.
        with self.assertRaises(author.ProfileError):
            author.serialize({"routing": {"expires_at": "soon"}})
        author.serialize({"routing": {"expires_at": "2026-01-01T00:00:00Z"}})

    def test_the_spelling_rule_reaches_the_fields_2_2_names_and_no_further(self):
        # This asserted the opposite until E-36 was raised: any string with an
        # RFC 3339 spelling that was not §2.2's was refused wherever it sat, on
        # the reasoning that "a wrong spelling is a wrong spelling". The
        # reasoning presumes the string is a timestamp, and §2.6 says a
        # predicate's `public_context` may mean anything at all -- so an offset
        # spelling there is the predicate's data, not a malformed §2.2 value.
        #
        # The rule was never in `spec/`. E-23 settled the *spelling* and its
        # reach over `routing`, which §4 step 8 compares byte for byte; it did
        # not settle whether §2.2 binds every string. Until E-36 does, this tool
        # produces what §2.2 states and no more.
        author.serialize({"public_context": {"a": "2026-01-01t00:00:00z"}})
        # The field-name rule is unaffected: it is what §2.2 actually says.
        with self.assertRaises(author.ProfileError):
            author.serialize({"issued_at": "2026-01-01t00:00:00z"})

    def test_a_leap_second_serializes(self):
        # RFC 3339 §5.7 permits it and §2.2 does not exclude it.
        self.assertIn(b"2016-12-31T23:59:60Z",
                      author.serialize({"t": "2016-12-31T23:59:60Z"}))

    def test_the_one_permitted_spelling_serializes(self):
        self.assertIn(b'"2026-01-01T00:00:00Z"',
                      author.serialize({"issued_at": "2026-01-01T00:00:00Z"}))

    def test_a_float_in_the_payload_is_refused(self):
        with self.assertRaises(author.ProfileError):
            self.signed({"capacity": 1.5})

    def test_running_without_self_test_explains_usage(self):
        self.assertEqual(author.main(["author_vectors.py"]), 2)


if __name__ == "__main__":
    unittest.main()
