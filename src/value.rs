//! The value model a signed Q2D structure is built from, and its serializer.
//!
//! [P-002](https://github.com/q2d-protocol/q2d/blob/main/docs/prds/P-002-message-envelope.md)
//! §4.2 defines a deterministic production profile, and §4.3 prohibits
//! floating-point in any signed structure. This module is both.
//!
//! ## Why there is no float variant
//!
//! §4.3 says a float reaching the serializer *"is a programming error and fails
//! loudly"*, and the interface in §5 describes `serialize_core` as erroring on
//! one. A [`Value`] that cannot hold a float fails louder: the error is a
//! compile error, and there is no runtime path to test because there is no
//! runtime path.
//!
//! That does not remove the check, it moves it. Bytes arriving from outside —
//! a payload being parsed — can contain a float, and the parser is where that
//! is refused. Serialization is downstream of a value that exists, and by then
//! the question has been settled by the type.
//!
//! The point of the prohibition is not tidiness. IEEE-754 rendering differs
//! between languages, so one float field would make two implementations emit
//! different bytes for the same logical message, and the Stage 1 gate compares
//! bytes. §4.3 removes that from the protocol rather than managing it.
//!
//! ## Why the serializer is not a canonicalizer
//!
//! §4.1: producers **must** emit this profile; verifiers **must not** depend on
//! it. A signature covers the exact bytes transmitted, so nothing verifies by
//! re-deriving them — and a verifier that re-serialized would put a
//! canonicalization dependency back into the security path, which is what
//! signing received bytes exists to remove.
//!
//! So this is a *production* rule. It exists because two producers building the
//! same logical query must agree byte for byte, not because anything reads the
//! bytes back.

use crate::timestamp;
use std::collections::BTreeMap;

/// A value that can appear in a signed Q2D structure.
///
/// The JSON model minus floating-point, and minus anything else no signed
/// structure contains. `Integer` is `i64` because every numeric field in the
/// protocol is a count, a cardinality, or a capacity in integer millibits
/// (`core-model.md` §3.1).
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Value {
    Null,
    Bool(bool),
    Integer(i64),
    String(String),
    Array(Vec<Value>),
    /// A `BTreeMap` rather than an insertion-ordered map, so a caller cannot
    /// make two objects that differ only in the order they were built, and a
    /// duplicate key is impossible by construction.
    ///
    /// Its iteration order is *not* §4.2's order — `Ord for String` compares
    /// UTF-8 bytes, which is Unicode scalar order, and §4.2 asks for UTF-16
    /// code-unit order. The two differ above the BMP. [`serialize`] sorts.
    Object(BTreeMap<String, Value>),
}

impl Value {
    /// An object from pairs, for call sites that would otherwise be noisy.
    pub fn object<K: Into<String>, I: IntoIterator<Item = (K, Value)>>(pairs: I) -> Value {
        Value::Object(pairs.into_iter().map(|(k, v)| (k.into(), v)).collect())
    }

    /// A string value.
    pub fn string<S: Into<String>>(s: S) -> Value {
        Value::String(s.into())
    }
}

/// Serialize under P-002 §4.2's deterministic production profile.
///
/// UTF-8, no whitespace between tokens, keys ascending, absent optionals
/// omitted rather than nulled, integers without exponent or leading zeros, and
/// minimal string escaping.
///
/// §5 names this `serialize_core` and gives it a `CoreObject`. `CoreObject` does
/// not exist yet, and the profile is a property of the value model rather than
/// of any one message type, so this is the general form and `serialize_core`
/// becomes the typed wrapper.
///
/// # Errors
///
/// §4.3's float ban needs no check here — [`Value`] has no float variant, so a
/// float is a compile error. What remains is `core-model.md` §2.2's timestamp,
/// which §4.2 cites: this is the last point at which a value can be refused
/// before it becomes bytes somebody signs, and inside a signed payload a
/// malformed timestamp is past the reach of anything that reads it as text.
pub fn serialize(value: &Value) -> Result<Vec<u8>, ProfileError> {
    let mut out = String::new();
    write(value, true, &mut out)?;
    Ok(out.into_bytes())
}

/// A value the production profile refuses to turn into bytes.
///
/// Carries no private data: every message names a field or a spelling, both of
/// which the caller supplied and neither of which is an answer.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ProfileError(pub String);

impl std::fmt::Display for ProfileError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(&self.0)
    }
}

impl std::error::Error for ProfileError {}

/// `protocol_level` is §2.2's *"the core object, `routing`, and a receipt"*: the
/// nesting at which a field name carries a `core-model.md` meaning. It starts
/// true and stays true only through [`PROTOCOL_SUBOBJECTS`], because a
/// `public_context` field called `receipt` is the predicate's own structure and
/// §2.6 says that may mean anything at all.
///
/// [`PROTOCOL_SUBOBJECTS`]: crate::timestamp::PROTOCOL_SUBOBJECTS
fn write(value: &Value, protocol_level: bool, out: &mut String) -> Result<(), ProfileError> {
    match value {
        Value::Null => out.push_str("null"),
        Value::Bool(true) => out.push_str("true"),
        Value::Bool(false) => out.push_str("false"),
        // `i64`'s `Display` is exactly §4.2's integer rule: no exponent, no
        // leading `+`, no leading zeros. Nothing to configure and nothing two
        // languages can render differently.
        Value::Integer(n) => out.push_str(&n.to_string()),
        Value::String(s) => {
            // By shape, at any depth: a string that has some RFC 3339 spelling
            // but not §2.2's is a malformed timestamp wherever it appears, and
            // `public_context` is exactly where an unexpected one would arrive.
            if timestamp::looks_like_rfc3339(s) && !timestamp::is_q2d_timestamp(s) {
                return Err(ProfileError(format!(
                    "timestamp {s:?} is not core-model.md §2.2's — uppercase `T`, \
                     uppercase `Z`, second precision, and a real instant. Checking \
                     the spelling alone would pass '2026-99-99T99:99:99Z', which has \
                     the right shape and is no date"
                )));
            }
            write_string(s, out);
        }
        Value::Array(items) => {
            out.push('[');
            for (i, item) in items.iter().enumerate() {
                if i > 0 {
                    out.push(',');
                }
                // An array is not a protocol level of its own: §2.2 names
                // objects, and a timestamp field's value is not an array.
                write(item, false, out)?;
            }
            out.push(']');
        }
        Value::Object(pairs) => {
            out.push('{');
            // Sorted rather than taken in `BTreeMap` order: that is Unicode
            // scalar order, and §4.2 asks for UTF-16 code-unit order. The two
            // differ above the BMP, where UTF-16 uses a surrogate pair
            // beginning at 0xD800 -- below U+E000..U+FFFF, so a supplementary
            // key sorts *before* one that scalar order puts first.
            //
            // No field name in `core-model.md` §2 is outside ASCII, so the
            // protocol does not reach the difference today. Sorting anyway,
            // because the alternative is a serializer that agrees with the
            // other two until the first non-ASCII key and then disagrees about
            // signed bytes -- which would read as a specification dispute.
            let mut keys: Vec<&String> = pairs.keys().collect();
            keys.sort_by(|a, b| utf16_units(a).cmp(&utf16_units(b)));
            for (i, key) in keys.iter().enumerate() {
                let item = &pairs[*key];
                if i > 0 {
                    out.push(',');
                }
                // By name as well as by shape, so a malformed timestamp in a
                // field `core-model.md` gives one is caught however malformed.
                // `2026-1-01T00:00:00Z` has no RFC 3339 shape at all and is
                // still a timestamp field, and so is `42`.
                if protocol_level && timestamp::TIMESTAMP_FIELDS.contains(&key.as_str()) {
                    let spelling = match item {
                        Value::String(s) => s,
                        other => {
                            return Err(ProfileError(format!(
                                "{key} is a timestamp field and {} is not a string. \
                                 core-model.md §2.2's timestamp is one",
                                type_name(other)
                            )))
                        }
                    };
                    if !timestamp::is_q2d_timestamp(spelling) {
                        return Err(ProfileError(format!(
                            "{key} is a timestamp field and {spelling:?} is not \
                             core-model.md §2.2's timestamp — uppercase `T`, uppercase \
                             `Z`, second precision, and a real instant"
                        )));
                    }
                }
                write_string(key, out);
                out.push(':');
                let nested =
                    protocol_level && timestamp::PROTOCOL_SUBOBJECTS.contains(&key.as_str());
                write(item, nested, out)?;
            }
            out.push('}');
        }
    }
    Ok(())
}

/// A value's JSON type, for an error message. Never its contents — §4.3's
/// sibling rule is that no private value reaches an error string.
fn type_name(value: &Value) -> &'static str {
    match value {
        Value::Null => "null",
        Value::Bool(_) => "a boolean",
        Value::Integer(_) => "an integer",
        Value::String(_) => "a string",
        Value::Array(_) => "an array",
        Value::Object(_) => "an object",
    }
}

/// A key's UTF-16 code units, which is what §4.2 orders by.
///
/// Allocating per comparison is the slow way to do this and the clear one; §4.2
/// is a correctness rule and objects here have a handful of keys. Performance
/// is a Stage 8 concern (`CLAUDE.md`), and a hand-rolled comparator that walked
/// both strings' code units in step would be the thing a reviewer has to check.
fn utf16_units(s: &str) -> Vec<u16> {
    s.encode_utf16().collect()
}

/// A JSON string under §4.2's *minimal escaping* rule.
///
/// Escaped: what RFC 8259 §7 requires — the quote, the backslash, and the
/// control characters below U+0020. Nothing else. A `\uXXXX` escape for a
/// character that can be written directly would be a second valid encoding of
/// the same string, and two producers choosing differently is the divergence
/// this profile exists to prevent.
fn write_string(s: &str, out: &mut String) {
    out.push('"');
    for c in s.chars() {
        match c {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            // The five two-character escapes RFC 8259 names, preferred over the
            // six-character \u form for the same reason as above: one encoding
            // of a character, not two.
            '\u{8}' => out.push_str("\\b"),
            '\u{c}' => out.push_str("\\f"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            c if (c as u32) < 0x20 => out.push_str(&format!("\\u{:04x}", c as u32)),
            c => out.push(c),
        }
    }
    out.push('"');
}

#[cfg(test)]
mod tests {
    use super::*;

    fn text(value: &Value) -> String {
        let bytes = serialize(value).expect("nothing here is refused by the profile");
        String::from_utf8(bytes).expect("the profile emits UTF-8")
    }

    #[test]
    fn keys_are_ascending_whatever_order_they_were_given() {
        let value = Value::object([
            ("type", Value::string("query")),
            ("q2d_version", Value::string("0.1")),
            ("nonce", Value::string("x")),
        ]);
        assert_eq!(
            text(&value),
            r#"{"nonce":"x","q2d_version":"0.1","type":"query"}"#
        );
    }

    #[test]
    fn there_is_no_whitespace_between_tokens() {
        let value = Value::object([
            (
                "a",
                Value::Array(vec![Value::Integer(1), Value::Integer(2)]),
            ),
            ("b", Value::object([("c", Value::Null)])),
        ]);
        assert_eq!(text(&value), r#"{"a":[1,2],"b":{"c":null}}"#);
    }

    #[test]
    fn integers_carry_no_exponent_sign_or_leading_zero() {
        for (n, rendered) in [
            (0, "0"),
            (-1, "-1"),
            (1000000, "1000000"),
            (i64::MIN, "-9223372036854775808"),
        ] {
            assert_eq!(text(&Value::Integer(n)), rendered);
        }
    }

    #[test]
    fn strings_escape_only_what_must_be_escaped() {
        // §4.2: no `\uXXXX` for characters representable directly. A profile
        // that escaped non-ASCII would emit two valid encodings of one string.
        assert_eq!(text(&Value::string("é😀")), "\"é😀\"");
        assert_eq!(text(&Value::string("a\"b\\c")), r#""a\"b\\c""#);
        assert_eq!(text(&Value::string("\n\t\r")), r#""\n\t\r""#);
        // A control character with no two-character escape takes the \u
        // form: lowercase hex, four digits, which is the only spelling
        // this profile emits.
        assert_eq!(text(&Value::string("\u{1}")), r#""\u0001""#);
    }

    #[test]
    fn an_absent_optional_is_absent_rather_than_null() {
        // The profile cannot express "present and null" by accident: a field is
        // in the map or it is not. This test records the distinction rather
        // than exercising a branch -- P-002 issue 1's acceptance is that the
        // two are distinguishable, and here they are different documents.
        let absent = Value::object([("a", Value::Integer(1))]);
        let null = Value::object([("a", Value::Integer(1)), ("b", Value::Null)]);
        assert_eq!(text(&absent), r#"{"a":1}"#);
        assert_eq!(text(&null), r#"{"a":1,"b":null}"#);
        assert_ne!(text(&absent), text(&null));
    }

    #[test]
    fn keys_sort_by_utf16_code_unit_not_by_scalar_value() {
        // The one case where §4.2's ordering differs from the container's:
        // UTF-16 encodes a supplementary character as a surrogate pair
        // beginning at 0xD800, which is below U+FFFD, so it sorts first --
        // where scalar order, which is what `BTreeMap<String>` iterates in,
        // puts it last.
        //
        // Nothing in `core-model.md` §2 has a non-ASCII field name, so the
        // protocol does not reach this today. It is implemented so that the day
        // something does, the two implementations already agree -- this is
        // `value_test.go`'s `TestKeysSortByUTF16CodeUnit`, asserting the same
        // bytes.
        let value = Value::object([
            ("\u{FFFD}", Value::Integer(1)),
            ("\u{10000}", Value::Integer(2)),
        ]);
        assert_eq!(text(&value), "{\"\u{10000}\":2,\"\u{FFFD}\":1}");

        // And the container really does disagree, so the assertion above is
        // testing the serializer rather than restating the map.
        let raw: Vec<&str> = match &value {
            Value::Object(pairs) => pairs.keys().map(String::as_str).collect(),
            _ => unreachable!(),
        };
        assert_eq!(raw, ["\u{FFFD}", "\u{10000}"]);
    }

    #[test]
    fn an_empty_object_and_an_empty_array_have_one_form_each() {
        assert_eq!(text(&Value::object(Vec::<(&str, Value)>::new())), "{}");
        assert_eq!(text(&Value::Array(vec![])), "[]");
    }
}
