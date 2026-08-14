//! Bytes back into a [`Value`], for payloads whose signature already verified.
//!
//! ## What this must accept
//!
//! **Any valid JSON that the value model can hold** — not only what
//! [`crate::serialize`] produces. P-002 §4.1: *producers must emit the
//! deterministic profile; verifiers must not depend on it.* A parser that
//! required the profile would reject a conforming implementation's payload for
//! putting a space after a colon, and would make verification depend on
//! canonicalization, which is the dependency signing received bytes exists to
//! remove.
//!
//! So whitespace, key order, and the choice between `\u00e9` and a literal `é`
//! are all accepted. P-002 issue 11's vector is a payload that verifies and is
//! *not* profile-conformant, and it exists to prove exactly this.
//!
//! ## What this must refuse
//!
//! - **Duplicate keys.** §4.2 prohibits them on production and requires
//!   rejection on parse. A parser taking last-wins or first-wins gives two
//!   implementations two readings of one payload, and the payload is signed —
//!   so both readings carry a valid signature.
//! - **Floats.** §4.3, and [`Value`] has no variant for one.
//! - **An integer outside `i64`.** `scope.md` §4.1's range (E-37).
//! - **Anything JSON itself refuses**, which is most of this file's length:
//!   trailing bytes, a raw control character in a string, a lone surrogate, a
//!   leading zero.
//!
//! ## What it does not own
//!
//! The §4.8 limits are P-002 issue 5's, on `parse_envelope`. This carries one
//! of them — a depth bound — because recursive descent without one is a stack
//! overflow on hostile input, and *verified* is not *trusted*: a signature says
//! who sent the bytes, not that they meant well.
//!
//! And it is **not** the parser in `src/bin/q2d-conform.rs`, which reads vector
//! files. That is a different format with different rules: a vector is not a
//! signed structure, so §4.3 does not reach it and a float in one is legal.
//! Sharing them would make the runner refuse a corpus file the corpus format
//! permits, to satisfy a rule about payloads.

use crate::value::Value;
use std::collections::BTreeMap;

/// The nesting bound, from P-002 §4.8. Stated here so this parser is safe on
/// its own; issue 5 applies the full set — size, depth, and member count —
/// at the envelope, before allocation.
const MAX_DEPTH: usize = 16;

/// Bytes that are not a [`Value`].
///
/// Carries a byte offset and never a value: the offset is a fact about the
/// input's shape, which the sender chose, where the bytes at it may be a
/// private field of a response.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ParseError(pub String);

impl std::fmt::Display for ParseError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(&self.0)
    }
}

impl std::error::Error for ParseError {}

/// Parse a payload whose signature has already been verified.
///
/// §5 names this `parse_core` and gives it a `CoreObject`. `CoreObject` does
/// not exist yet, so this is the general form, exactly as [`crate::serialize`]
/// is — and `parse_core` becomes the typed wrapper that also checks §2.2's
/// timestamp fields and §2's required ones.
///
/// Taking bytes rather than a string is deliberate: a payload arrives as bytes
/// and its encoding is this function's to check, not its caller's to promise.
pub fn parse(bytes: &[u8]) -> Result<Value, ParseError> {
    let text = std::str::from_utf8(bytes).map_err(|e| {
        ParseError(format!(
            "not valid UTF-8 at byte {}. P-002 §4.2's profile is UTF-8 and \
             RFC 8259 §8.1 requires it for exchanged JSON",
            e.valid_up_to()
        ))
    })?;
    let mut parser = Parser {
        bytes: text.as_bytes(),
        at: 0,
        depth: 0,
    };
    parser.skip_whitespace();
    let value = parser.value()?;
    parser.skip_whitespace();
    if parser.at != parser.bytes.len() {
        return Err(parser.fail("trailing bytes after the value"));
    }
    Ok(value)
}

struct Parser<'a> {
    bytes: &'a [u8],
    at: usize,
    depth: usize,
}

impl<'a> Parser<'a> {
    fn fail(&self, what: &str) -> ParseError {
        ParseError(format!("{what}, at byte {}", self.at))
    }

    fn peek(&self) -> Option<u8> {
        self.bytes.get(self.at).copied()
    }

    fn skip_whitespace(&mut self) {
        // RFC 8259 §2's four, and only those. A parser that also skipped a
        // vertical tab would accept bytes another implementation rejects.
        while matches!(self.peek(), Some(b' ' | b'\t' | b'\n' | b'\r')) {
            self.at += 1;
        }
    }

    fn expect(&mut self, byte: u8) -> Result<(), ParseError> {
        if self.peek() == Some(byte) {
            self.at += 1;
            Ok(())
        } else {
            Err(self.fail(&format!("expected {:?}", byte as char)))
        }
    }

    fn literal(&mut self, word: &str, value: Value) -> Result<Value, ParseError> {
        if self.bytes[self.at..].starts_with(word.as_bytes()) {
            self.at += word.len();
            Ok(value)
        } else {
            Err(self.fail("not a JSON value"))
        }
    }

    fn value(&mut self) -> Result<Value, ParseError> {
        match self.peek() {
            Some(b'{') => self.object(),
            Some(b'[') => self.array(),
            Some(b'"') => self.string().map(Value::String),
            Some(b't') => self.literal("true", Value::Bool(true)),
            Some(b'f') => self.literal("false", Value::Bool(false)),
            Some(b'n') => self.literal("null", Value::Null),
            Some(b'-' | b'0'..=b'9') => self.number(),
            Some(_) => Err(self.fail("not a JSON value")),
            None => Err(self.fail("input ended where a value was expected")),
        }
    }

    fn nested<T>(&mut self, body: impl FnOnce(&mut Self) -> T) -> Result<T, ParseError> {
        self.depth += 1;
        if self.depth > MAX_DEPTH {
            return Err(self.fail(&format!(
                "nested deeper than P-002 §4.8's limit of {MAX_DEPTH}"
            )));
        }
        let out = body(self);
        self.depth -= 1;
        Ok(out)
    }

    fn object(&mut self) -> Result<Value, ParseError> {
        self.expect(b'{')?;
        self.nested(|p| {
            let mut pairs: BTreeMap<String, Value> = BTreeMap::new();
            p.skip_whitespace();
            if p.peek() == Some(b'}') {
                p.at += 1;
                return Ok(Value::Object(pairs));
            }
            loop {
                p.skip_whitespace();
                let key = p.string()?;
                p.skip_whitespace();
                p.expect(b':')?;
                p.skip_whitespace();
                let item = p.value()?;
                // §4.2: rejected on parse, not resolved. The name is the
                // sender's own and is safe to repeat; nothing about the value
                // is.
                if pairs.insert(key.clone(), item).is_some() {
                    return Err(p.fail(&format!(
                        "duplicate key {key:?}, which P-002 §4.2 rejects rather \
                         than resolving — two readings of one signed payload"
                    )));
                }
                p.skip_whitespace();
                match p.peek() {
                    Some(b',') => p.at += 1,
                    Some(b'}') => {
                        p.at += 1;
                        return Ok(Value::Object(pairs));
                    }
                    _ => return Err(p.fail("expected ',' or '}'")),
                }
            }
        })?
    }

    fn array(&mut self) -> Result<Value, ParseError> {
        self.expect(b'[')?;
        self.nested(|p| {
            let mut items = Vec::new();
            p.skip_whitespace();
            if p.peek() == Some(b']') {
                p.at += 1;
                return Ok(Value::Array(items));
            }
            loop {
                p.skip_whitespace();
                items.push(p.value()?);
                p.skip_whitespace();
                match p.peek() {
                    Some(b',') => p.at += 1,
                    Some(b']') => {
                        p.at += 1;
                        return Ok(Value::Array(items));
                    }
                    _ => return Err(p.fail("expected ',' or ']'")),
                }
            }
        })?
    }

    fn string(&mut self) -> Result<String, ParseError> {
        self.expect(b'"')?;
        let mut out = String::new();
        loop {
            let byte = match self.peek() {
                Some(b) => b,
                None => return Err(self.fail("input ended inside a string")),
            };
            match byte {
                b'"' => {
                    self.at += 1;
                    return Ok(out);
                }
                b'\\' => {
                    self.at += 1;
                    self.escape(&mut out)?;
                }
                // RFC 8259 §7: a character below U+0020 must be escaped. A
                // parser that passed one through would accept bytes the
                // profile cannot produce and another implementation refuses.
                0x00..=0x1F => return Err(self.fail("unescaped control character in a string")),
                _ => {
                    // The input is already known to be UTF-8, so this
                    // advances by whole characters rather than bytes.
                    let rest = &self.bytes[self.at..];
                    let text = std::str::from_utf8(rest).expect("checked at entry");
                    let c = text.chars().next().expect("non-empty");
                    out.push(c);
                    self.at += c.len_utf8();
                }
            }
        }
    }

    fn escape(&mut self, out: &mut String) -> Result<(), ParseError> {
        let byte = match self.peek() {
            Some(b) => b,
            None => return Err(self.fail("input ended inside an escape")),
        };
        self.at += 1;
        let simple = match byte {
            b'"' => '"',
            b'\\' => '\\',
            b'/' => '/',
            b'b' => '\u{8}',
            b'f' => '\u{c}',
            b'n' => '\n',
            b'r' => '\r',
            b't' => '\t',
            b'u' => return self.unicode_escape(out),
            _ => return Err(self.fail("unknown escape")),
        };
        out.push(simple);
        Ok(())
    }

    fn unicode_escape(&mut self, out: &mut String) -> Result<(), ParseError> {
        let first = self.hex4()?;
        // A surrogate pair is two escapes and one character. Accepted because
        // RFC 8259 §7 describes it and a conforming producer that escapes a
        // supplementary character has no other spelling; a *lone* surrogate is
        // refused, because it is not a character and has no UTF-8 encoding.
        let scalar = if (0xD800..0xDC00).contains(&first) {
            if !self.bytes[self.at..].starts_with(b"\\u") {
                return Err(self.fail("high surrogate with no low surrogate after it"));
            }
            self.at += 2;
            let second = self.hex4()?;
            if !(0xDC00..0xE000).contains(&second) {
                return Err(self.fail("high surrogate followed by a non-surrogate"));
            }
            0x10000 + ((u32::from(first) - 0xD800) << 10) + (u32::from(second) - 0xDC00)
        } else if (0xDC00..0xE000).contains(&first) {
            return Err(self.fail("low surrogate with no high surrogate before it"));
        } else {
            u32::from(first)
        };
        match char::from_u32(scalar) {
            Some(c) => {
                out.push(c);
                Ok(())
            }
            None => Err(self.fail("escape names no character")),
        }
    }

    fn hex4(&mut self) -> Result<u16, ParseError> {
        if self.at + 4 > self.bytes.len() {
            return Err(self.fail("input ended inside a \\u escape"));
        }
        let digits = &self.bytes[self.at..self.at + 4];
        if !digits.iter().all(u8::is_ascii_hexdigit) {
            return Err(self.fail("\\u escape is not four hex digits"));
        }
        let text = std::str::from_utf8(digits).expect("ascii");
        self.at += 4;
        u16::from_str_radix(text, 16).map_err(|_| self.fail("\\u escape is not four hex digits"))
    }

    fn number(&mut self) -> Result<Value, ParseError> {
        let start = self.at;
        if self.peek() == Some(b'-') {
            self.at += 1;
        }
        // RFC 8259 §6: one leading zero, or digits not starting with zero.
        match self.peek() {
            Some(b'0') => self.at += 1,
            Some(b'1'..=b'9') => {
                while matches!(self.peek(), Some(b'0'..=b'9')) {
                    self.at += 1;
                }
            }
            _ => return Err(self.fail("a number needs a digit")),
        }

        // A fraction or an exponent makes it a float **syntactically**, and
        // that is the test — not whether the value happens to be integral.
        //
        // `1e2` is a hundred and no conforming producer emits it; §4.2's
        // integers carry no exponent. Deciding that it *is* a hundred means
        // exponent arithmetic, and `1e400` means deciding in what — the
        // float-precision divergence §4.3 removes from the protocol rather
        // than managing. A syntactic test is decidable identically in every
        // language, which is the property that matters here.
        if matches!(self.peek(), Some(b'.' | b'e' | b'E')) {
            return Err(self.fail(
                "a fraction or exponent, which P-002 §4.3 prohibits in a signed \
                 structure — capacity is integer millibits, timestamps are strings",
            ));
        }

        let text = std::str::from_utf8(&self.bytes[start..self.at]).expect("ascii digits");
        text.parse::<i64>().map(Value::Integer).map_err(|_| {
            ParseError(format!(
                "integer outside −2^63 … 2^63 − 1, which scope.md §4.1 requires \
                 an entry's integers to lie within, at byte {start}"
            ))
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::serialize;

    fn parsed(text: &str) -> Value {
        parse(text.as_bytes()).unwrap_or_else(|e| panic!("{text}: {e}"))
    }

    fn refused(text: &str) -> String {
        match parse(text.as_bytes()) {
            Err(e) => e.to_string(),
            Ok(_) => panic!("{text}: parsed, and must not"),
        }
    }

    #[test]
    fn a_payload_round_trips() {
        // P-002 issue 4's acceptance: `parse_core(serialize_core(x)) == x`.
        let value = Value::object([
            ("q2d_version", Value::string("0.1")),
            ("n", Value::Integer(-42)),
            ("empty", Value::object(Vec::<(&str, Value)>::new())),
            (
                "list",
                Value::Array(vec![Value::Null, Value::Bool(true), Value::string("é😀")]),
            ),
        ]);
        let bytes = serialize(&value).expect("a conforming value");
        assert_eq!(parse(&bytes).expect("its own output"), value);
    }

    #[test]
    fn a_non_conformant_payload_still_parses() {
        // §4.1's whole point, and P-002 issue 11's vector in miniature: a
        // verifier must not require the production profile. Whitespace, key
        // order, an escaped character that need not be escaped, and `/`
        // escaped — none of which this profile emits.
        let value = parsed("{ \"b\" : 2,\n  \"a\"\t: \"\\u00e9\\/\" }");
        assert_eq!(
            value,
            Value::object([("a", Value::string("é/")), ("b", Value::Integer(2))])
        );
        // And it re-serializes to the profile, which is what makes the two
        // directions independent.
        assert_eq!(
            String::from_utf8(serialize(&value).unwrap()).unwrap(),
            r#"{"a":"é/","b":2}"#
        );
    }

    #[test]
    fn a_duplicate_key_is_refused() {
        let message = refused(r#"{"a":1,"a":2}"#);
        assert!(message.contains("duplicate key"), "{message}");
        // The name is repeated and the values are not: a key is the sender's
        // own label, and `2` could be an answer.
        assert!(message.contains(r#""a""#));
        assert!(!message.contains("2,"), "{message}");
    }

    #[test]
    fn a_float_is_refused_however_it_is_written() {
        for text in ["1.5", "[0.0]", "1e2", "1E2", "-2.0e-3", r#"{"a":1.0}"#] {
            let message = refused(text);
            assert!(message.contains("§4.3"), "{text}: {message}");
        }
    }

    #[test]
    fn an_integer_outside_the_range_is_refused() {
        assert!(refused("9223372036854775808").contains("§4.1"));
        assert!(refused("-9223372036854775809").contains("§4.1"));
        // The boundaries themselves parse.
        assert_eq!(parsed("9223372036854775807"), Value::Integer(i64::MAX));
        assert_eq!(parsed("-9223372036854775808"), Value::Integer(i64::MIN));
    }

    #[test]
    fn json_the_grammar_refuses_is_refused() {
        for text in [
            "",
            "  ",
            "{",
            "[1",
            "{\"a\"}",
            "{\"a\":}",
            "[1,]",
            "{,}",
            "nul",
            "tru",
            // Numbers RFC 8259 §6 does not admit.
            "01",
            "+1",
            ".5",
            "1.",
            "-",
            "1e",
            "0x10",
            // Two values, one document.
            "1 2",
            "{} {}",
            "\"a\" \"b\"",
            // Strings.
            "\"unterminated",
            "\"\\q\"",
            "\"\\u00\"",
            "\"\\uZZZZ\"",
        ] {
            refused(text);
        }
    }

    #[test]
    fn a_raw_control_character_in_a_string_is_refused() {
        // RFC 8259 §7 requires it escaped, and the profile emits it escaped —
        // so accepting it here would admit bytes no producer can make.
        assert!(refused("\"a\u{1}b\"").contains("control character"));
        assert!(refused("\"a\nb\"").contains("control character"));
        // Escaped, the same character is fine and round-trips.
        assert_eq!(parsed(r#""a\u0001b""#), Value::string("a\u{1}b"));
    }

    #[test]
    fn a_surrogate_pair_is_one_character_and_a_lone_one_is_none() {
        assert_eq!(parsed(r#""\ud83d\ude00""#), Value::string("😀"));
        for lone in [
            r#""\ud800""#,
            r#""\udc00""#,
            r#""\ud800\ud800""#,
            r#""\ud800x""#,
        ] {
            let message = refused(lone);
            assert!(message.contains("surrogate"), "{lone}: {message}");
        }
    }

    #[test]
    fn invalid_utf8_is_refused_before_anything_else() {
        let message = match parse(&[b'"', 0x80, b'"']) {
            Err(e) => e.to_string(),
            Ok(_) => panic!("parsed invalid UTF-8"),
        };
        assert!(message.contains("UTF-8"), "{message}");
    }

    #[test]
    fn nesting_past_the_limit_is_refused_rather_than_overflowing() {
        // Verified is not trusted: a signature says who sent the bytes, not
        // that they meant well. Recursive descent without a bound is a stack
        // overflow, which is a crash rather than a rejection.
        let deep = "[".repeat(MAX_DEPTH) + &"]".repeat(MAX_DEPTH);
        parse(deep.as_bytes()).expect("exactly the limit");

        let deeper = "[".repeat(MAX_DEPTH + 1) + &"]".repeat(MAX_DEPTH + 1);
        assert!(refused(&deeper).contains("§4.8"));

        // And the crash this prevents, at a depth no bound-free parser
        // survives on a small stack.
        let absurd = "[".repeat(100_000);
        assert!(refused(&absurd).contains("§4.8"));
    }

    #[test]
    fn an_error_names_a_position_and_never_a_value() {
        // A byte offset is a fact about the input's shape, which the sender
        // chose. The bytes at it may be a private field of a response.
        let message = refused(r#"{"answer":"the value that must not leak",}"#);
        assert!(message.contains("byte"), "{message}");
        assert!(!message.contains("must not leak"), "{message}");
    }
}
