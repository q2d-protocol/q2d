//! The Rust conformance runner: implements the contract, answers nothing yet.
//!
//! ```text
//! q2d-conform <vector-file.json>   →  result JSON on stdout
//! ```
//!
//! See `conformance/RUNNER-CONTRACT.md`. This is the Rust half of the pair
//! `harness cross` compares. It exists before either implementation does, so
//! that the contract is demonstrably implementable in both languages and so
//! that P-001 issue 19's cross-verification has two runners to put an artefact
//! between.
//!
//! **It implements no Q2D behaviour, and adding some is a deliberate act.**
//! Every operation reports `error`. What it does implement is the half of the
//! contract that is not protocol: read the projection, parse it as RFC 8259
//! JSON rather than as what a library tolerates, recognise the operation or
//! exit 1, and emit a well-formed result. That much has to be right, because
//! the harness is entitled to assume it.
//!
//! Unlike `conformance/runners/stub/`, this one *may* learn to answer — it is
//! the reference implementation's runner, and the corpus exists to be run
//! against it. The stub may not, because it shares an author with the harness.
//!
//! **No dependencies.** The JSON scanner below is hand-written because a runner
//! must reject what RFC 8259 rejects, and the two things a permissive parser
//! waves through — `NaN`/`Infinity`, and duplicate object keys — are exactly
//! what the contract names. Reaching for a crate would make that behaviour
//! somebody else's default rather than this runner's decision, and the decision
//! is the point. It is also why `CONVENTIONS-rust.md` does not exist yet:
//! dependency policy is a Stage 1 question and nothing here needs it answered.

use std::collections::BTreeSet;
use std::fmt;
use std::process::ExitCode;

const NAME: &str = "q2d-rust";
const VERSION: &str = "0.0.0";

const EXIT_RESULT_PRODUCED: u8 = 0;
const EXIT_CANNOT_PROCESS: u8 = 1;
const EXIT_INTERNAL: u8 = 2;

/// P-001 §6's `VectorInput`, and nothing else.
const PROJECTED_FIELDS: [&str; 3] = ["id", "operation", "input"];

/// P-001 §4.5's vocabulary, embedded rather than read from `vector.schema.json`.
///
/// A runner reads the vector it was given and nothing else. One that consulted
/// the schema would answer differently depending on the checkout it ran in, and
/// this binary ships without the corpus beside it. Drift is caught where it
/// should be: an operation a runner does not recognise is exit 1 and the vector
/// fails loudly.
const KNOWN_OPERATIONS: [&str; 11] = [
    "sign_query",
    "sign_response",
    "verify_query",
    "verify_response",
    "digest",
    "resolve_predicate",
    "effective_domain",
    "capacity_debit",
    "policy_decide",
    "evaluate_predicate",
    "process_query",
];

/// Just enough of a JSON value to answer the contract's questions.
///
/// The runner needs two things from a vector — which fields the top-level
/// object carries, and the string values of `id` and `operation` — but it has
/// to *validate* all of it, because a duplicate key three levels down is still
/// a vector it must refuse.
///
/// `Bool` and `Array` carry nothing: the runner never reads a boolean or an
/// array element, and a variant that held one would invite a later reader to
/// start comparing values here — which is the protocol behaviour this binary
/// deliberately does not have. They exist so the parser can *validate* them.
#[derive(Debug)]
enum Json {
    Null,
    Bool,
    Number,
    String(String),
    Array,
    Object(Vec<(String, Json)>),
}

impl Json {
    fn as_str(&self) -> Option<&str> {
        match self {
            Json::String(s) => Some(s),
            _ => None,
        }
    }

    fn get(&self, key: &str) -> Option<&Json> {
        match self {
            Json::Object(pairs) => pairs.iter().find(|(k, _)| k == key).map(|(_, v)| v),
            _ => None,
        }
    }

    fn keys(&self) -> BTreeSet<&str> {
        match self {
            Json::Object(pairs) => pairs.iter().map(|(k, _)| k.as_str()).collect(),
            _ => BTreeSet::new(),
        }
    }
}

#[derive(Debug)]
struct ParseError(String);

impl fmt::Display for ParseError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.0)
    }
}

struct Parser<'a> {
    bytes: &'a [u8],
    at: usize,
}

impl<'a> Parser<'a> {
    fn new(text: &'a str) -> Self {
        Parser { bytes: text.as_bytes(), at: 0 }
    }

    fn err<T>(&self, what: &str) -> Result<T, ParseError> {
        Err(ParseError(format!("{what} at byte {}", self.at)))
    }

    fn skip_whitespace(&mut self) {
        while let Some(b) = self.bytes.get(self.at) {
            // RFC 8259 §2: these four and no others. A parser that also skipped
            // a form feed would accept documents the specification does not.
            if matches!(b, b' ' | b'\t' | b'\n' | b'\r') {
                self.at += 1;
            } else {
                break;
            }
        }
    }

    fn peek(&self) -> Option<u8> {
        self.bytes.get(self.at).copied()
    }

    fn expect(&mut self, b: u8) -> Result<(), ParseError> {
        if self.peek() == Some(b) {
            self.at += 1;
            Ok(())
        } else {
            self.err(&format!("expected {:?}", b as char))
        }
    }

    fn literal(&mut self, word: &str) -> Result<(), ParseError> {
        if self.bytes[self.at..].starts_with(word.as_bytes()) {
            self.at += word.len();
            Ok(())
        } else {
            self.err(&format!("expected {word}"))
        }
    }

    fn document(&mut self) -> Result<Json, ParseError> {
        self.skip_whitespace();
        let value = self.value()?;
        self.skip_whitespace();
        if self.at != self.bytes.len() {
            return self.err("trailing content after the JSON document");
        }
        Ok(value)
    }

    fn value(&mut self) -> Result<Json, ParseError> {
        match self.peek() {
            Some(b'{') => self.object(),
            Some(b'[') => self.array(),
            Some(b'"') => Ok(Json::String(self.string()?)),
            Some(b't') => self.literal("true").map(|()| Json::Bool),
            Some(b'f') => self.literal("false").map(|()| Json::Bool),
            Some(b'n') => self.literal("null").map(|()| Json::Null),
            // The two the contract names. They are not JSON, and a parser that
            // accepts them lets a vector carry a value no other implementation
            // can read.
            Some(b'N') | Some(b'I') => self.err("NaN and Infinity are not JSON"),
            Some(b'-') if self.bytes.get(self.at + 1) == Some(&b'I') => {
                self.err("NaN and Infinity are not JSON")
            }
            Some(b) if b == b'-' || b.is_ascii_digit() => self.number(),
            Some(_) => self.err("not a JSON value"),
            None => self.err("unexpected end of input"),
        }
    }

    fn object(&mut self) -> Result<Json, ParseError> {
        self.expect(b'{')?;
        let mut pairs: Vec<(String, Json)> = Vec::new();
        self.skip_whitespace();
        if self.peek() == Some(b'}') {
            self.at += 1;
            return Ok(Json::Object(pairs));
        }
        loop {
            self.skip_whitespace();
            let key = self.string()?;
            // RFC 8259 permits repeated names and says the behaviour is
            // unpredictable; a runner that kept the last would answer a vector
            // its judge read differently. Refusing is the only reading two
            // implementations can share.
            if pairs.iter().any(|(k, _)| *k == key) {
                return self.err(&format!("duplicate object key {key:?}"));
            }
            self.skip_whitespace();
            self.expect(b':')?;
            self.skip_whitespace();
            let value = self.value()?;
            pairs.push((key, value));
            self.skip_whitespace();
            match self.peek() {
                Some(b',') => self.at += 1,
                Some(b'}') => {
                    self.at += 1;
                    return Ok(Json::Object(pairs));
                }
                _ => return self.err("expected ',' or '}'"),
            }
        }
    }

    fn array(&mut self) -> Result<Json, ParseError> {
        self.expect(b'[')?;
        self.skip_whitespace();
        if self.peek() == Some(b']') {
            self.at += 1;
            return Ok(Json::Array);
        }
        loop {
            self.skip_whitespace();
            // Validated and dropped: every element must be JSON, and none of
            // them is anything this runner reads.
            self.value()?;
            self.skip_whitespace();
            match self.peek() {
                Some(b',') => self.at += 1,
                Some(b']') => {
                    self.at += 1;
                    return Ok(Json::Array);
                }
                _ => return self.err("expected ',' or ']'"),
            }
        }
    }

    fn string(&mut self) -> Result<String, ParseError> {
        self.expect(b'"')?;
        let mut out = String::new();
        loop {
            let b = match self.peek() {
                Some(b) => b,
                None => return self.err("unterminated string"),
            };
            self.at += 1;
            match b {
                b'"' => return Ok(out),
                b'\\' => {
                    let esc = match self.peek() {
                        Some(e) => e,
                        None => return self.err("unterminated escape"),
                    };
                    self.at += 1;
                    match esc {
                        b'"' => out.push('"'),
                        b'\\' => out.push('\\'),
                        b'/' => out.push('/'),
                        b'b' => out.push('\u{8}'),
                        b'f' => out.push('\u{c}'),
                        b'n' => out.push('\n'),
                        b'r' => out.push('\r'),
                        b't' => out.push('\t'),
                        b'u' => {
                            let hex = self
                                .bytes
                                .get(self.at..self.at + 4)
                                .ok_or_else(|| ParseError("truncated \\u escape".into()))?;
                            let hex = std::str::from_utf8(hex)
                                .map_err(|_| ParseError("invalid \\u escape".into()))?;
                            let code = u32::from_str_radix(hex, 16)
                                .map_err(|_| ParseError("invalid \\u escape".into()))?;
                            self.at += 4;
                            out.push(self.scalar_from(code)?);
                        }
                        _ => return self.err("unknown escape"),
                    }
                }
                // RFC 8259 §7: unescaped control characters are not permitted.
                0x00..=0x1f => return self.err("unescaped control character in string"),
                _ => {
                    // Copy the UTF-8 sequence this byte begins.
                    let start = self.at - 1;
                    let len = utf8_len(b);
                    let end = start + len;
                    let slice = self
                        .bytes
                        .get(start..end)
                        .ok_or_else(|| ParseError("truncated UTF-8 sequence".into()))?;
                    let s = std::str::from_utf8(slice)
                        .map_err(|_| ParseError("invalid UTF-8 in string".into()))?;
                    out.push_str(s);
                    self.at = end;
                }
            }
        }
    }

    /// One Unicode scalar from a `\u` escape, joining a surrogate pair.
    ///
    /// RFC 8259 §7 encodes a character outside the BMP as two escapes, and a
    /// runner that rejected the first half would refuse a document the other
    /// runner accepts -- a divergence about JSON, which is exactly what
    /// `harness cross` must never be reporting. A *lone* surrogate is still
    /// refused: it is not a character, and it cannot be written back out.
    fn scalar_from(&mut self, code: u32) -> Result<char, ParseError> {
        const HIGH: std::ops::Range<u32> = 0xd800..0xdc00;
        const LOW: std::ops::Range<u32> = 0xdc00..0xe000;

        if LOW.contains(&code) {
            return self.err("a low surrogate with no high surrogate before it");
        }
        if !HIGH.contains(&code) {
            return char::from_u32(code)
                .ok_or_else(|| ParseError("invalid \\u escape".into()));
        }
        if self.peek() != Some(b'\\') || self.bytes.get(self.at + 1) != Some(&b'u') {
            return self.err("a high surrogate with no low surrogate after it");
        }
        self.at += 2;
        let hex = self
            .bytes
            .get(self.at..self.at + 4)
            .ok_or_else(|| ParseError("truncated \\u escape".into()))?;
        let hex = std::str::from_utf8(hex)
            .map_err(|_| ParseError("invalid \\u escape".into()))?;
        let low = u32::from_str_radix(hex, 16)
            .map_err(|_| ParseError("invalid \\u escape".into()))?;
        if !LOW.contains(&low) {
            return self.err("a high surrogate followed by something that is not a low one");
        }
        self.at += 4;
        let combined = 0x10000 + ((code - 0xd800) << 10) + (low - 0xdc00);
        char::from_u32(combined).ok_or_else(|| ParseError("invalid surrogate pair".into()))
    }

    /// RFC 8259 §6's grammar, walked directly.
    ///
    /// ```text
    /// number = [ minus ] int [ frac ] [ exp ]
    /// int    = zero / ( digit1-9 *DIGIT )
    /// frac   = "." 1*DIGIT
    /// exp    = ("e" / "E") [ minus / plus ] 1*DIGIT
    /// ```
    ///
    /// Not `f64::from_str`, which accepts `01`, `1.` and `.5` — forms the RFC
    /// forbids and `encoding/json` refuses. Delegating to a float parser would
    /// have let this runner answer a projection the Go one rejects, which is
    /// the divergence-about-encoding `harness cross` must never report. The
    /// value is never kept: the runner has no use for it, and holding one would
    /// invite it to be compared as a float.
    fn number(&mut self) -> Result<Json, ParseError> {
        if self.peek() == Some(b'-') {
            self.at += 1;
        }
        match self.peek() {
            // A leading zero admits no more digits: `01` is two tokens, not one
            // number.
            Some(b'0') => self.at += 1,
            Some(b) if b.is_ascii_digit() => {
                while matches!(self.peek(), Some(b) if b.is_ascii_digit()) {
                    self.at += 1;
                }
            }
            _ => return self.err("a number needs at least one digit"),
        }
        if self.peek() == Some(b'.') {
            self.at += 1;
            if !matches!(self.peek(), Some(b) if b.is_ascii_digit()) {
                return self.err("a fraction needs at least one digit");
            }
            while matches!(self.peek(), Some(b) if b.is_ascii_digit()) {
                self.at += 1;
            }
        }
        if matches!(self.peek(), Some(b'e') | Some(b'E')) {
            self.at += 1;
            if matches!(self.peek(), Some(b'+') | Some(b'-')) {
                self.at += 1;
            }
            if !matches!(self.peek(), Some(b) if b.is_ascii_digit()) {
                return self.err("an exponent needs at least one digit");
            }
            while matches!(self.peek(), Some(b) if b.is_ascii_digit()) {
                self.at += 1;
            }
        }
        Ok(Json::Number)
    }
}

fn utf8_len(first: u8) -> usize {
    match first {
        0x00..=0x7f => 1,
        0xc0..=0xdf => 2,
        0xe0..=0xef => 3,
        _ => 4,
    }
}

/// The result object, written by hand for the same reason the parser is.
fn escape(s: &str) -> String {
    let mut out = String::with_capacity(s.len() + 2);
    for c in s.chars() {
        match c {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            c if (c as u32) < 0x20 => out.push_str(&format!("\\u{:04x}", c as u32)),
            c => out.push(c),
        }
    }
    out
}

fn fail(message: &str, code: u8) -> ExitCode {
    eprintln!("q2d-conform: {message}");
    ExitCode::from(code)
}

fn run(args: &[String]) -> ExitCode {
    if args.len() != 2 {
        return fail("usage: q2d-conform <vector-file.json>", EXIT_CANNOT_PROCESS);
    }

    let text = match std::fs::read_to_string(&args[1]) {
        Ok(text) => text,
        Err(e) => return fail(&format!("cannot read the vector: {e}"), EXIT_CANNOT_PROCESS),
    };
    let vector = match Parser::new(&text).document() {
        Ok(v) => v,
        Err(e) => return fail(&format!("cannot read the vector: {e}"), EXIT_CANNOT_PROCESS),
    };

    if !matches!(vector, Json::Object(_)) {
        return fail("the vector file is not an object", EXIT_CANNOT_PROCESS);
    }
    // Both present *and* strings. A non-string `id` copied into `vector_id`
    // would be a result the harness cannot judge — the runner reporting that it
    // functioned when it did not.
    for field in ["id", "operation"] {
        if vector.get(field).and_then(Json::as_str).is_none() {
            return fail(
                &format!("the vector carries no string {field}"),
                EXIT_CANNOT_PROCESS,
            );
        }
    }

    let present = vector.keys();
    let missing: Vec<&str> = PROJECTED_FIELDS
        .iter()
        .copied()
        .filter(|f| !present.contains(f))
        .collect();
    if !missing.is_empty() {
        return fail(
            &format!("the vector carries no {}", missing.join(", ")),
            EXIT_CANNOT_PROCESS,
        );
    }
    let extra: Vec<&str> = present
        .iter()
        .copied()
        .filter(|k| !PROJECTED_FIELDS.contains(k))
        .collect();
    if !extra.is_empty() {
        // The extra field that matters is `expect`. A runner holding an
        // expectation was handed the authored vector, so the harness failed to
        // project it — and the corpus stops being evidence the moment an
        // implementation can read the answer. Refusing is the second lock on a
        // door the harness holds the first key to.
        if extra.contains(&"expect") {
            return fail(
                "the vector carries an expectation -- it was not projected; \
                 refusing to answer a vector whose answer it was given",
                EXIT_CANNOT_PROCESS,
            );
        }
        return fail(
            &format!("the vector carries unexpected field(s): {}", extra.join(", ")),
            EXIT_CANNOT_PROCESS,
        );
    }

    let operation = vector.get("operation").and_then(Json::as_str).unwrap();
    if !KNOWN_OPERATIONS.contains(&operation) {
        return fail(
            &format!("unknown operation {operation:?}"),
            EXIT_CANNOT_PROCESS,
        );
    }

    // A result was produced, so exit 0. The vector fails on its outcome, which
    // is the harness's call and not this runner's.
    let id = vector.get("id").and_then(Json::as_str).unwrap();
    println!(
        "{{\"detail\":\"{}\",\"implementation\":{{\"name\":\"{}\",\"version\":\"{}\"}},\
         \"outcome\":\"error\",\"vector_id\":\"{}\"}}",
        escape("the Rust runner implements no Q2D behaviour yet"),
        escape(NAME),
        escape(VERSION),
        escape(id)
    );
    ExitCode::from(EXIT_RESULT_PRODUCED)
}

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().collect();
    match std::panic::catch_unwind(|| run(&args)) {
        Ok(code) => code,
        // The contract's exit 2: a fault so early that no result could be
        // written. Distinguished from exit 1 so the harness can tell "this
        // runner cannot process the vector" from "this runner broke".
        Err(_) => fail("internal error", EXIT_INTERNAL),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn parse(text: &str) -> Result<Json, ParseError> {
        Parser::new(text).document()
    }

    #[test]
    fn duplicate_keys_are_refused() {
        assert!(parse(r#"{"a":1,"a":2}"#).is_err());
        assert!(parse(r#"{"outer":{"a":1,"a":2}}"#).is_err(),
                "a duplicate three levels down is still a vector to refuse");
    }

    #[test]
    fn nan_and_infinity_are_refused() {
        for text in ["NaN", "Infinity", "-Infinity", r#"{"x":NaN}"#] {
            assert!(parse(text).is_err(), "{text} is not JSON");
        }
    }

    #[test]
    fn trailing_content_is_refused() {
        assert!(parse(r#"{"a":1} {"b":2}"#).is_err());
    }

    #[test]
    fn control_characters_must_be_escaped() {
        assert!(parse("\"a\nb\"").is_err());
        assert!(parse(r#""a\nb""#).is_ok());
    }

    #[test]
    fn only_rfc_8259_numbers_are_accepted() {
        for text in ["0", "-0", "1", "-1.5", "1e10", "1E-10", "0.5", "12345"] {
            assert!(parse(&format!("{{\"x\":{text}}}")).is_ok(), "{text} is a number");
        }
        // Every one of these is accepted by `f64::from_str` and refused by
        // `encoding/json`, which is why the grammar is walked rather than
        // delegated.
        for text in ["01", "1.", ".5", "+1", "-", "1e", "1e+", "00", "0x1"] {
            assert!(parse(&format!("{{\"x\":{text}}}")).is_err(),
                    "{text} is not an RFC 8259 number");
        }
    }

    #[test]
    fn a_projection_parses() {
        let v = parse(r#"{"id":"message/sign/x","operation":"sign_query","input":{}}"#)
            .expect("a valid projection");
        assert_eq!(v.get("id").and_then(Json::as_str), Some("message/sign/x"));
        assert_eq!(v.keys().len(), 3);
    }

    #[test]
    fn the_operation_vocabulary_matches_the_projected_field_count() {
        // Guards the two constants against a careless edit: the contract fixes
        // VectorInput at exactly three fields, and P-001 §4.5's Stage 1-4
        // vocabulary at eleven operations.
        assert_eq!(PROJECTED_FIELDS.len(), 3);
        assert_eq!(KNOWN_OPERATIONS.len(), 11);
    }
}
