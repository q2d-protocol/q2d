//! The envelope, and P-002 §4.8's limits applied where the shape allows.
//!
//! ```text
//! { "signed": "<JWS compact>", "routing": { … } }
//! ```
//!
//! `signed` is opaque here. Its internal structure is P-003's; this layer
//! treats it as a string and never inspects it — §4.4.
//!
//! ## Where each limit lands
//!
//! §4 step 1 says *before any allocation on attacker-controlled data*, and the
//! whole-envelope bound is the one that delivers it: 64 KiB, checked on the
//! byte slice before a parser is constructed. Everything after it is bounded by
//! that, so the later checks are about *shape* rather than about exhaustion.
//!
//! Two of §4.8's five rows cannot be enforced at step 1, and the envelope's own
//! shape is why:
//!
//! - **`public_context` — 32 KiB.** It is inside the signed payload, which is
//!   base64url text at this layer. Reading it here would mean decoding and
//!   parsing an unverified payload, which §4's order exists to prevent: parsing
//!   happens at step 5, after verification at step 4. The limit belongs to
//!   `parse_core`, and P-002 §4.8 now says so.
//!
//! - **Any single string — 2 KiB.** It cannot reach `signed`. A JWS compact of
//!   the canonical query is about 1.6 KiB before any public context, so a 2 KiB
//!   cap on that member would leave a few hundred bytes for the predicate's
//!   data and the protocol could not carry its own worked example. `signed` is
//!   bounded by the envelope limit; the 2 KiB applies to every other string,
//!   which here means `routing`'s.

use crate::parse::{parse_within, ParseError, MAX_ENVELOPE, MAX_STRING};
use crate::value::Value;

/// A parsed envelope.
///
/// `routing` is optional, and §2.1 now says so: *"`routing` may be absent, and
/// a responder must accept a message carrying only `signed`"*. It exists for a
/// party that need not be there — a direct exchange has no intermediary to
/// dispatch, and requiring the projection would put `predicate.id` and
/// `target.custodian` in the clear for nobody's benefit. E-38, closed as B.
///
/// This is one of the few places the *permissive* reading is the safe one.
/// Absence removes no guarantee: everything the signature covers is still
/// covered, and a projection that is present is the thing that can disagree.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Envelope {
    pub signed: String,
    pub routing: Option<Value>,
}

/// Parse an envelope under §4.8's limits.
///
/// # Errors
///
/// Oversized input, anything [`crate::parse`] refuses, a missing or non-string
/// `signed`, a non-object `routing`, a member that is neither, or a string in
/// `routing` above 2 KiB.
///
/// A member that is neither is refused rather than ignored: an envelope is two
/// fields, and a third is either a version this build does not know or an
/// attempt to have one party read what another does not. Both deny.
pub fn parse_envelope(bytes: &[u8]) -> Result<Envelope, ParseError> {
    // First, and on the slice: this is the check §4 step 1 asks for, and it is
    // the only one that runs before anything is allocated from the input.
    if bytes.len() > MAX_ENVELOPE {
        return Err(ParseError(format!(
            "envelope of {} bytes, above P-002 §4.8's limit of {MAX_ENVELOPE}",
            bytes.len()
        )));
    }

    // `MAX_ENVELOPE` as the string bound, not `MAX_STRING`: `signed` is a whole
    // JWS compact string and the envelope limit is what bounds it. Nothing is
    // unbounded — a string here cannot exceed the envelope that contains it.
    let value = parse_within(bytes, MAX_ENVELOPE)?;

    let pairs = match value {
        Value::Object(pairs) => pairs,
        _ => return Err(ParseError("an envelope is a JSON object".into())),
    };

    let mut signed = None;
    let mut routing = None;
    // By UTF-16 code unit, not `BTreeMap` order, which is by Unicode scalar
    // value. The two differ above the BMP, so an envelope with two unknown
    // members named U+10000 and U+E000 would be reported by a different one
    // here than in Go. A rejection reason two implementations disagree about is
    // a divergence even when both reject — the same rule §4.2 states for keys,
    // applied to the order they are *examined* in.
    let mut ordered: Vec<(String, Value)> = pairs.into_iter().collect();
    ordered.sort_by_key(|(key, _)| key.encode_utf16().collect::<Vec<u16>>());
    for (key, item) in ordered {
        match (key.as_str(), item) {
            ("signed", Value::String(text)) => signed = Some(text),
            ("signed", _) => {
                return Err(ParseError("`signed` is a JWS compact string — §4.4".into()))
            }
            ("routing", item @ Value::Object(_)) => routing = Some(item),
            ("routing", _) => {
                return Err(ParseError(
                    "`routing` is an object of projected fields — §4.5".into(),
                ))
            }
            // The name is the sender's own structure rather than a value, and
            // an envelope has no operation-defined members for it to be data
            // from: §4.4 gives the envelope two fields and P-003 owns what is
            // inside `signed`.
            (other, _) => {
                return Err(ParseError(format!(
                    "unknown envelope member {other:?} — §4.4 has `signed` and `routing`"
                )))
            }
        }
    }

    let signed = signed.ok_or_else(|| ParseError("no `signed` member — §4.4".into()))?;

    // §4.8's 2 KiB, over the part of the envelope it can reach. Post-parse
    // rather than during, because the parser applied the envelope bound to
    // every string so that `signed` would fit; this narrows the rest back.
    // Bounded work: the envelope was capped before any of it was read.
    if let Some(len) = routing.as_ref().and_then(longest_string) {
        if len > MAX_STRING {
            return Err(ParseError(format!(
                "a `routing` string of {len} bytes, above P-002 §4.8's {MAX_STRING}"
            )));
        }
    }

    Ok(Envelope { signed, routing })
}

/// The longest string anywhere in a value, in bytes.
fn longest_string(value: &Value) -> Option<usize> {
    match value {
        Value::String(text) => Some(text.len()),
        Value::Array(items) => items.iter().filter_map(longest_string).max(),
        // Keys as well as values: a key is a string field of the object, and a
        // relay that read a 3 KiB member name has held it either way.
        Value::Object(pairs) => pairs
            .iter()
            .flat_map(|(key, item)| [Some(key.len()), longest_string(item)])
            .flatten()
            .max(),
        _ => None,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn envelope(text: &str) -> Envelope {
        parse_envelope(text.as_bytes()).unwrap_or_else(|e| panic!("{text}: {e}"))
    }

    fn refused(text: &str) -> String {
        match parse_envelope(text.as_bytes()) {
            Err(e) => e.to_string(),
            Ok(_) => panic!("parsed, and must not: {text}"),
        }
    }

    #[test]
    fn an_envelope_is_both_of_2_1_s_parts() {
        let one = envelope(r#"{"signed":"aGVhZGVy.cGF5bG9hZA.c2ln","routing":{}}"#);
        assert_eq!(one.signed, "aGVhZGVy.cGF5bG9hZA.c2ln");
        assert_eq!(
            one.routing,
            Some(Value::object(Vec::<(&str, Value)>::new()))
        );

        let two = envelope(r#"{"signed":"a.b.c","routing":{"type":"query"}}"#);
        assert_eq!(
            two.routing,
            Some(Value::object([("type", Value::string("query"))]))
        );
    }

    #[test]
    fn an_envelope_without_routing_is_accepted() {
        // §2.1, as E-38 closed it: "`routing` may be absent, and a responder
        // must accept a message carrying only `signed`."
        //
        // Absent and empty are still different, and both are legal. An empty
        // `routing` is a projection of nothing, which §4.6 compares field by
        // field and finds no field to compare; an absent one is no projection.
        assert_eq!(envelope(r#"{"signed":"a.b.c"}"#).routing, None);
        assert_eq!(
            envelope(r#"{"signed":"a.b.c","routing":{}}"#).routing,
            Some(Value::object(Vec::<(&str, Value)>::new()))
        );
    }

    #[test]
    fn a_missing_or_mistyped_member_is_refused() {
        assert!(refused(r#"{"routing":{}}"#).contains("no `signed`"));
        assert!(refused(r#"{"signed":42,"routing":{}}"#).contains("`signed`"));
        assert!(refused(r#"{"signed":"a.b.c","routing":[]}"#).contains("`routing`"));
        assert!(refused("[]").contains("JSON object"));
    }

    #[test]
    fn an_unknown_member_denies_rather_than_being_ignored() {
        // Unknown, missing and indeterminate all deny. Ignoring it would let
        // one party read a field another does not.
        let message = refused(r#"{"signed":"a.b.c","routing":{},"hint":"trust me"}"#);
        assert!(message.contains("unknown envelope member"), "{message}");
        assert!(message.contains("hint"), "{message}");
    }

    #[test]
    fn an_oversized_envelope_is_refused_on_its_length() {
        // The §4 step 1 check: on the slice, before a parser exists. The input
        // is deliberately not valid JSON, so a parser reaching it at all would
        // report something else.
        let huge = vec![b'x'; MAX_ENVELOPE + 1];
        let message = match parse_envelope(&huge) {
            Err(e) => e.to_string(),
            Ok(_) => panic!("parsed an oversized envelope"),
        };
        assert!(message.contains("§4.8"), "{message}");
        assert!(message.contains("envelope of"), "{message}");
    }

    #[test]
    fn signed_may_be_larger_than_a_string_field_and_routing_may_not() {
        // The reading §4.8 leaves open, and the arithmetic that settles it: a
        // JWS compact of the canonical query is about 1.6 KiB before any
        // public context, so a 2 KiB cap on `signed` would make the protocol
        // unable to carry its own worked example.
        let long = "s".repeat(MAX_STRING * 4);
        envelope(&format!(r#"{{"signed":"{long}","routing":{{}}}}"#));

        let message = refused(&format!(
            r#"{{"signed":"a.b.c","routing":{{"custodian":"{long}"}}}}"#
        ));
        assert!(message.contains("§4.8"), "{message}");
        assert!(message.contains("routing"), "{message}");
    }

    #[test]
    fn a_routing_key_counts_as_a_string_too() {
        let long = "k".repeat(MAX_STRING + 1);
        let message = refused(&format!(r#"{{"signed":"a.b.c","routing":{{"{long}":1}}}}"#));
        assert!(message.contains("§4.8"), "{message}");
    }

    #[test]
    fn the_parser_s_own_limits_still_apply() {
        // Depth and members are enforced during the parse, so an envelope gets
        // them without this function repeating the checks.
        let deep = format!(
            r#"{{"signed":"a.b.c","routing":{}}}"#,
            "[".repeat(20) + &"]".repeat(20)
        );
        assert!(refused(&deep).contains("§4.8"));

        let members: Vec<String> = (0..65).map(|i| format!(r#""k{i}":{i}"#)).collect();
        let wide = format!(
            r#"{{"signed":"a.b.c","routing":{{{}}}}}"#,
            members.join(",")
        );
        assert!(refused(&wide).contains("members"));
    }

    #[test]
    fn the_payload_is_not_inspected() {
        // §4.4: `signed` is opaque here. This one is not valid base64url and
        // not a JWS, and the envelope layer has no opinion — P-003 does, at
        // step 3, and the ordering is the point.
        assert_eq!(
            envelope(r#"{"signed":"not a jws at all","routing":{}}"#).signed,
            "not a jws at all"
        );
    }
}
