//! `q2d_version`, checked at §4 step 5 and before anything else is read.
//!
//! ## One version, inside the signed object
//!
//! P-002 §10's second question, resolved: the envelope carries no version of
//! its own. A separate envelope version would be **unsigned** and therefore
//! rewritable by any intermediary, and two version numbers for one message is a
//! negotiation surface `core-model.md` §1 does not have — there is no round
//! trip in which a requester could discover which one a responder honours.
//!
//! §5.2.1 puts `unsupported_version` at **step 5** for the same reason: the
//! authoritative value is inside the signed object, so it cannot be read before
//! verification at step 4. `routing` may carry a copy and §4 step 2 may shed
//! stale traffic on it, but that is load shedding and never a rejection reason
//! — which is why this function takes the *verified core object* and has no
//! parameter for a projection.
//!
//! ## Rejecting without interpreting is the whole rule
//!
//! A responder that read the rest of an unknown-version message to produce a
//! better error has interpreted fields whose meaning it does not know. Version
//! *n+1* may move a field, change its type, or give the same name another
//! sense; a diagnostic built by reading them is a guess presented as fact, and
//! the guess is made on attacker-controlled input.
//!
//! This function reads exactly one key. That is the property, and it is
//! structural rather than a discipline a caller keeps.

use crate::value::Value;

/// The version this build implements.
///
/// One value, not a range. A range implies a negotiation, and §1 has none.
pub const SUPPORTED: &str = "0.1";

/// A message this build will not interpret.
///
/// Carries no value: `q2d_version` is the sender's own claim, and an unknown
/// one is exactly the field this build has no vocabulary for. §5.2.1's external
/// value is `unsupported_version`, which P-009 emits; this is the internal one.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct UnsupportedVersion;

impl std::fmt::Display for UnsupportedVersion {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(
            f,
            "`q2d_version` is absent or not {SUPPORTED} — core-model.md §4 step 5"
        )
    }
}

impl std::error::Error for UnsupportedVersion {}

/// Whether this build interprets the verified core object.
///
/// Absent, not a string, and any other value all reject: unknown, missing and
/// indeterminate deny.
pub fn check_version(core: &Value) -> Result<(), UnsupportedVersion> {
    let version = match core {
        Value::Object(pairs) => pairs.get("q2d_version"),
        _ => None,
    };
    match version {
        Some(Value::String(text)) if text == SUPPORTED => Ok(()),
        _ => Err(UnsupportedVersion),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_supported_version_passes() {
        let core = Value::object([
            ("q2d_version", Value::string(SUPPORTED)),
            ("type", Value::string("query")),
        ]);
        assert_eq!(check_version(&core), Ok(()));
    }

    #[test]
    fn everything_else_denies() {
        // Unknown, missing and indeterminate all deny. A version this build
        // does not implement is not a thing to negotiate: §1 has no round trip
        // in which to negotiate it.
        for core in [
            // A version from the future, and one from a past that never was.
            Value::object([("q2d_version", Value::string("0.2"))]),
            Value::object([("q2d_version", Value::string("0.0"))]),
            // Prefixes and suffixes, which a `starts_with` check would admit.
            Value::object([("q2d_version", Value::string("0.10"))]),
            Value::object([("q2d_version", Value::string("0.1.0"))]),
            Value::object([("q2d_version", Value::string(" 0.1"))]),
            Value::object([("q2d_version", Value::string("0.1 "))]),
            // The number rather than the string: §2.2's field is a string, and
            // a check that coerced would accept a shape the profile refuses.
            Value::object([("q2d_version", Value::Integer(0))]),
            Value::object([("q2d_version", Value::Null)]),
            // Absent, and not an object at all.
            Value::object([("type", Value::string("query"))]),
            Value::Null,
            Value::Array(vec![]),
        ] {
            assert_eq!(check_version(&core), Err(UnsupportedVersion), "{core:?}");
        }
    }

    #[test]
    fn an_unknown_version_rejects_without_reading_anything_else() {
        // The rule this issue exists for. Every other field here is wrong in a
        // way some later step would catch — a malformed timestamp, a missing
        // `type`, a `predicate` that is a string — and none of that is
        // consulted, because version *n+1* may have moved or retyped any of
        // them and a diagnostic built by reading them is a guess presented as
        // fact.
        let nonsense = Value::object([
            ("q2d_version", Value::string("0.2")),
            ("issued_at", Value::string("not a date")),
            ("predicate", Value::string("not an object")),
            ("expires_at", Value::Integer(-1)),
        ]);
        assert_eq!(check_version(&nonsense), Err(UnsupportedVersion));

        // And the same object with a supported version passes *this* check,
        // which is what makes the assertion above about the version rather
        // than about the nonsense.
        let same_shape = Value::object([
            ("q2d_version", Value::string(SUPPORTED)),
            ("issued_at", Value::string("not a date")),
            ("predicate", Value::string("not an object")),
            ("expires_at", Value::Integer(-1)),
        ]);
        assert_eq!(check_version(&same_shape), Ok(()));
    }

    #[test]
    fn the_message_carries_no_value() {
        // `q2d_version` is the sender's claim, and an unknown one is exactly
        // the field this build has no vocabulary for — so repeating it in a log
        // line is repeating something unparsed. The message names the field and
        // the version this build *does* implement, both of which are ours.
        let message = UnsupportedVersion.to_string();
        assert!(message.contains("q2d_version"));
        assert!(message.contains(SUPPORTED));
    }
}
