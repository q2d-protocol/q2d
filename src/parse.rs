//! Bytes back into a [`Value`], for payloads whose signature already verified.
//!
//! ## What this must accept
//!
//! **Any valid JSON that the value model can hold** — not only what
//! [`crate::serialize`] produces. serialization.md §1: *producers must emit
//! the deterministic profile; verifiers must not depend on it.* A parser that
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
//! - **Duplicate keys.** serialization.md §2 rejects them rather than
//!   resolving them. A parser taking last-wins or first-wins gives two
//!   implementations two readings of one payload, and the payload is signed —
//!   so both readings carry a valid signature.
//! - **Floats.** serialization.md §2, and [`Value`] has no variant for one.
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
//! And it is **not** the parser in `src/bin/q2d-conform.rs`, which reads
//! vector files. That is a different format with different rules: a vector is
//! not a signed structure, so serialization.md §1 does not reach it and a
//! float in one is legal. Sharing them would make the runner refuse a corpus
//! file the corpus format permits, to satisfy a rule about payloads.

use crate::value::Value;
use std::collections::BTreeMap;

// P-002 §4.8's limits. Normative rather than advisory: a limit an
// implementation may choose is not a limit, and the two implementations must
// reject the same payload. Raising one is an escalation, because a limit that
// grows to fit a payload is not bounding anything.

/// Nesting depth.
pub const MAX_DEPTH: usize = 16;
/// Members per object.
pub const MAX_MEMBERS: usize = 64;
/// Any single string field the *specification defines*, in bytes. Bytes rather
/// than characters: it bounds what has to be held, and a character is one to
/// four of them.
///
/// §2.8 stops this at `predicate.public_context`, which §2.4 makes
/// operation-defined — so it is applied where protocol fields are known, which
/// is [`crate::parse_envelope`] for `routing` and `parse_core` for the payload.
pub const MAX_STRING: usize = 2 * 1024;

/// `predicate.public_context`, in bytes — and therefore the largest any single
/// string in a conforming message may be, since a string inside it cannot
/// exceed the object that holds it.
pub const MAX_PUBLIC_CONTEXT: usize = 32 * 1024;
/// The whole envelope, in bytes. Checked before parsing rather than during —
/// §4 step 1's *before any allocation on attacker-controlled data*.
pub const MAX_ENVELOPE: usize = 64 * 1024;

/// Bytes that are not a [`Value`].
///
/// Carries a byte offset and never a value: the offset is a fact about the
/// input's shape, which the sender chose, where the bytes at it may be a
/// private field of a response.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ParseError(pub String, pub ParseCause);

/// Why a parse failed, for a caller that has to report a reason.
///
/// The corpus asserts an **internal reason** per rejection, and
/// `message/reject/` distinguishes five parse failures that all reach
/// `malformed` on the wire. A caller cannot recover them from the message
/// string without matching prose, so the cause travels beside it.
///
/// `Other` is everything RFC 8259 itself refuses — a trailing comma, a lone
/// surrogate, a leading zero. Those are one fact to an operator ("this is not
/// JSON") and no vector distinguishes them.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ParseCause {
    DuplicateKey,
    Float,
    TooDeep,
    TooManyMembers,
    StringTooLong,
    IntegerOutOfRange,
    Other,
}

impl ParseError {
    /// A failure with no cause a caller distinguishes.
    pub(crate) fn other(message: impl Into<String>) -> Self {
        ParseError(message.into(), ParseCause::Other)
    }

    /// Why it failed.
    pub fn cause(&self) -> ParseCause {
        self.1
    }
}

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
    // §2.8's 2 KiB, everywhere except inside `predicate.public_context`, where
    // the bound is that object's own 32 KiB.
    //
    // Knowing where that subtree begins is protocol knowledge in a parser, and
    // it is the same knowledge [`crate::serialize`] already carries for §2.2's
    // field names — the mechanism is the mirror of its `protocol_level`. The
    // alternative was to bound every string at 32 KiB and owe the 2 KiB to a
    // `parse_core` that does not exist, which would accept protocol fields
    // §2.8 refuses.
    parse_within(bytes, Where::Root)
}

/// Where in a message the parser is, for §2.8's string bound.
///
/// The bound is 2 KiB for the fields the specification defines and 32 KiB
/// inside `predicate.public_context`, so the parser has to know which it is
/// looking at. Three states are enough: the path that matters is
/// `predicate` → `public_context`, and everything else is *elsewhere*.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum Where {
    /// The top of a message, where `predicate` is a protocol field.
    Root,
    /// Inside `predicate`, where `public_context` is the subtree that relaxes.
    Predicate,
    /// Inside `predicate.public_context`, or below it. §2.4 data.
    OperationDefined,
    /// Anywhere else — a protocol field, at §2.8's 2 KiB.
    Elsewhere,
    /// An envelope, where `signed` carries a whole payload and the envelope
    /// limit is what bounds it. [`crate::parse_envelope`] narrows `routing`
    /// back to 2 KiB afterwards, because at that layer it knows which is which.
    Envelope,
}

impl Where {
    fn max_string(self) -> usize {
        match self {
            Where::OperationDefined => MAX_PUBLIC_CONTEXT,
            Where::Envelope => MAX_ENVELOPE,
            _ => MAX_STRING,
        }
    }

    /// The state a member's value is parsed in.
    fn member(self, key: &str) -> Where {
        match (self, key) {
            (Where::Root, "predicate") => Where::Predicate,
            (Where::Predicate, "public_context") => Where::OperationDefined,
            (Where::OperationDefined, _) => Where::OperationDefined,
            (Where::Envelope, _) => Where::Envelope,
            _ => Where::Elsewhere,
        }
    }
}

/// The same, from a stated position in a message.
///
/// One caller besides [`parse`]: [`crate::parse_envelope`], because the
/// envelope's `signed` member is a whole JWS compact string and §2.8's 2 KiB
/// cannot reach it. See that function for the arithmetic.
pub(crate) fn parse_within(bytes: &[u8], where_: Where) -> Result<Value, ParseError> {
    let text = std::str::from_utf8(bytes).map_err(|e| {
        ParseError::other(format!(
            "not valid UTF-8 at byte {}. serialization.md §2 refuses these \
             rather than substituting, and RFC 8259 §8.1 requires UTF-8 for \
             exchanged JSON",
            e.valid_up_to()
        ))
    })?;
    let mut parser = Parser {
        bytes: text.as_bytes(),
        at: 0,
        depth: 0,
        where_,
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
    where_: Where,
}

impl<'a> Parser<'a> {
    /// Fail with a cause a caller can report. The five §5.2.1 collapses to
    /// `malformed` and the corpus keeps apart.
    fn fail_because(&self, cause: ParseCause, what: &str) -> ParseError {
        ParseError(format!("{what}, at byte {}", self.at), cause)
    }

    fn fail(&self, what: &str) -> ParseError {
        ParseError::other(format!("{what}, at byte {}", self.at))
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
            return Err(self.fail_because(
                ParseCause::TooDeep,
                &format!(
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
                // The value is parsed where the *key* puts it, and the parser
                // returns to where it was afterwards.
                let outer = p.where_;
                p.where_ = outer.member(&key);
                // §2.8 caps `predicate.public_context` **as a whole**, not each
                // string in it: two 20 KiB values are each under the per-string
                // bound and the object is not. Measured on the source span,
                // which is what the sender transmitted and what a relay held.
                let entering_public_context =
                    outer == Where::Predicate && p.where_ == Where::OperationDefined;
                let began = p.at;
                let item = p.value()?;
                if entering_public_context && p.at - began > MAX_PUBLIC_CONTEXT {
                    // `Other`, not `StringTooLong`: this is an **object**
                    // size, and no vector distinguishes it — the same reason
                    // an integer outside `i64` is `Other`. Tagging it as a
                    // string limit put Rust and Go on different internal
                    // reasons for one input, which review caught.
                    return Err(p.fail(&format!(
                        "`public_context` of {} bytes, above core-model.md \
                         §2.8's {MAX_PUBLIC_CONTEXT}",
                        p.at - began
                    )));
                }
                p.where_ = outer;
                // serialization.md §2: rejected on parse, not resolved.
                //
                // The key is **not** in the message. It reads as the sender's
                // own label, and on a query it is — but `parse` runs over
                // responses too, where a key inside a released `result` can be
                // derived from private data: a map keyed by a contact's name
                // discloses the name. The position is enough to find it, and a
                // position is a fact about the input's shape.
                if pairs.len() == MAX_MEMBERS {
                    return Err(p.fail_because(
                        ParseCause::TooManyMembers,
                        &format!("more than P-002 §4.8's {MAX_MEMBERS} members in one object"),
                    ));
                }
                if pairs.insert(key, item).is_some() {
                    return Err(p.fail_because(
                        ParseCause::DuplicateKey,
                        "duplicate key, which serialization.md §2 rejects \
                         rather than resolving — two readings of one signed \
                         payload",
                    ));
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
                    self.within_string_limit(&out)?;
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
                    self.within_string_limit(&out)?;
                }
            }
        }
    }

    /// §4.8's string bound, checked **as the string is built** rather than at
    /// its closing quote.
    ///
    /// Measured on the decoded string, not the source span: an escape is six
    /// source bytes and one character, and the decoded length is what has to be
    /// held. Checked per character because the point of a bound is to stop the
    /// allocation, and testing it at the end means a hostile payload has
    /// already made the parser hold the whole value — a limit enforced after
    /// the fact bounds what is *returned* and not what is *held*.
    ///
    /// The overshoot is at most one character, four bytes.
    fn within_string_limit(&self, out: &str) -> Result<(), ParseError> {
        if out.len() > self.where_.max_string() {
            return Err(self.fail_because(
                ParseCause::StringTooLong,
                &format!(
                "a string longer than core-model.md §2.8's {} bytes",
                self.where_.max_string()
            )));
        }
        Ok(())
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
        // `1e2` is a hundred and no conforming producer emits it;
        // serialization.md §1's integers carry no exponent. Deciding that it
        // *is* a hundred means exponent arithmetic, and `1e400` means deciding
        // in what — the float divergence serialization.md §1 removes
        // from the protocol rather than managing. A syntactic test is
        // decidable identically in every language, which is the property that
        // matters here.
        if matches!(self.peek(), Some(b'.' | b'e' | b'E')) {
            return Err(self.fail_because(
                ParseCause::Float,
                "a fraction or exponent, which serialization.md §2 refuses in \
                 a signed structure — capacity is integer millibits, \
                 timestamps are strings",
            ));
        }

        let text = std::str::from_utf8(&self.bytes[start..self.at]).expect("ascii digits");
        text.parse::<i64>().map(Value::Integer).map_err(|_| {
            ParseError(
                format!(
                    "integer outside −2^63 … 2^63 − 1, which scope.md §4.1 \
                     requires an entry's integers to lie within, at byte {start}"
                ),
                ParseCause::IntegerOutOfRange,
            )
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
        // serialization.md §2's point, and P-002 issue 11's vector in
        // miniature: a verifier must not require the production profile.
        // Whitespace, key order, an escaped character that need not be
        // escaped, and `/` escaped — none of which this profile emits.
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
        let message = refused(r#"{"secret_contact":1,"secret_contact":2}"#);
        assert!(message.contains("duplicate key"), "{message}");
        // Neither the key nor the value. A key reads as the sender's own
        // label, and on a response it can be derived from private data — a map
        // keyed by a contact's name discloses the name.
        assert!(!message.contains("secret_contact"), "{message}");
        assert!(message.contains("byte"), "{message}");
    }

    #[test]
    fn a_float_is_refused_however_it_is_written() {
        for text in ["1.5", "[0.0]", "1e2", "1E2", "-2.0e-3", r#"{"a":1.0}"#] {
            let message = refused(text);
            assert!(message.contains("serialization.md §2"), "{text}");
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
    fn a_protocol_string_is_bounded_at_2_kib_and_a_predicate_s_is_not() {
        // §2.8: the 2 KiB covers the fields the specification defines and stops
        // at `predicate.public_context`, which §2.4 leaves to the registered predicate.
        // The parser knows which is which — the same protocol knowledge
        // `serialize` carries for §2.2's field names.
        let three_kib = "d".repeat(3 * 1024);

        // A predicate's own description: accepted.
        let allowed = format!(r#"{{"predicate":{{"public_context":{{"note":"{three_kib}"}}}}}}"#);
        parse(allowed.as_bytes()).expect("§2.4 data, bounded by its entry");

        // The same string in a protocol field: refused.
        for refused_case in [
            format!(r#"{{"nonce":"{three_kib}"}}"#),
            format!(r#"{{"predicate":{{"id":"{three_kib}"}}}}"#),
            format!(r#"{{"purpose":{{"code":"{three_kib}"}}}}"#),
        ] {
            let message = refused(&refused_case);
            assert!(message.contains("§2.8"), "{message}");
        }

        // And `public_context` is not a magic word anywhere else: one nested
        // under a purpose is an ordinary protocol field.
        let elsewhere = format!(r#"{{"purpose":{{"public_context":"{three_kib}"}}}}"#);
        assert!(refused(&elsewhere).contains("§2.8"));
    }

    #[test]
    fn public_context_is_capped_as_a_whole_and_not_only_per_string() {
        // Two values each under the per-string bound, and an object over it.
        // A per-string check alone accepts this, which is the gap review found.
        let half = "d".repeat(20 * 1024);
        let case = format!(r#"{{"predicate":{{"public_context":{{"a":"{half}","b":"{half}"}}}}}}"#);
        let message = refused(&case);
        assert!(message.contains("public_context"), "{message}");
        assert!(message.contains("§2.8"), "{message}");

        // And an object comfortably inside it still parses.
        let small = "d".repeat(4 * 1024);
        let fits =
            format!(r#"{{"predicate":{{"public_context":{{"a":"{small}","b":"{small}"}}}}}}"#);
        parse(fits.as_bytes()).expect("well inside the limit");
    }

    #[test]
    fn even_a_predicate_s_string_is_bounded_by_public_context() {
        // Its own bound is its registry entry's `maxLength` (`scope.md` §4.1),
        // which this layer has no access to — so the backstop here is the
        // object's own 32 KiB.
        // Nothing is unbounded: past `public_context`'s own limit, no
        // conforming message can carry it, whoever defined the field.
        let too_long = "d".repeat(MAX_PUBLIC_CONTEXT + 1);
        let case = format!(r#"{{"predicate":{{"public_context":{{"note":"{too_long}"}}}}}}"#);
        assert!(refused(&case).contains("§2.8"));
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

#[cfg(test)]
mod cause_tests {
    use super::*;

    /// Each of the five must report its own cause, and the test builds the
    /// input for each rather than trusting where an edit landed.
    #[test]
    fn each_refusal_reports_its_own_cause() {
        let deep = format!("{}1{}", "[".repeat(20), "]".repeat(20));
        let wide = format!(
            "{{{}}}",
            (0..70).map(|i| format!("\"k{i}\":1")).collect::<Vec<_>>().join(",")
        );
        let long = format!("{{\"a\":\"{}\"}}", "x".repeat(3000));
        // A `public_context` above its object limit is `Other` in both
        // implementations: it is an object size, and no vector distinguishes
        // it. Rust tagged it as a string limit for one commit and Go did not,
        // which is a divergence on one input.
        let members: Vec<String> = (0..40)
            .map(|i| format!(r#""k{i}":"{}""#, "x".repeat(1000)))
            .collect();
        let context = format!(
            r#"{{"predicate":{{"public_context":{{{}}}}}}}"#,
            members.join(",")
        );
        for (input, expected) in [
            (context, ParseCause::Other),
            (r#"{"a":1,"a":2}"#.to_string(), ParseCause::DuplicateKey),
            (r#"{"a":1.5}"#.to_string(), ParseCause::Float),
            (deep, ParseCause::TooDeep),
            (wide, ParseCause::TooManyMembers),
            (long, ParseCause::StringTooLong),
            (r#"{"a":9223372036854775808}"#.to_string(), ParseCause::IntegerOutOfRange),
            (r#"{"a":}"#.to_string(), ParseCause::Other),
        ] {
            let error = parse(input.as_bytes()).unwrap_err();
            assert_eq!(error.cause(), expected, "{}", &input[..input.len().min(40)]);
        }
    }
}
