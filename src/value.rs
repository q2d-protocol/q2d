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
/// becomes the typed wrapper. Total, per §4.3: there is no float to fail on.
pub fn serialize(value: &Value) -> Vec<u8> {
    let mut out = String::new();
    write(value, &mut out);
    out.into_bytes()
}

fn write(value: &Value, out: &mut String) {
    match value {
        Value::Null => out.push_str("null"),
        Value::Bool(true) => out.push_str("true"),
        Value::Bool(false) => out.push_str("false"),
        // `i64`'s `Display` is exactly §4.2's integer rule: no exponent, no
        // leading `+`, no leading zeros. Nothing to configure and nothing two
        // languages can render differently.
        Value::Integer(n) => out.push_str(&n.to_string()),
        Value::String(s) => write_string(s, out),
        Value::Array(items) => {
            out.push('[');
            for (i, item) in items.iter().enumerate() {
                if i > 0 {
                    out.push(',');
                }
                write(item, out);
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
                write_string(key, out);
                out.push(':');
                write(item, out);
            }
            out.push('}');
        }
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
        String::from_utf8(serialize(value)).expect("the profile emits UTF-8")
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
