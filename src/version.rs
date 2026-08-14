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

/// Why a verified core object is not one this build interprets.
///
/// **Two variants because §5.2.1 gives them two external values.** That is the
/// opposite of `routing`'s two internal reasons, which both normalize to
/// `routing_mismatch` — there, collapsing them on the wire is the point; here,
/// collapsing them in the *internal* value would make the external one
/// unrecoverable, and a requester told `unsupported_version` about a message
/// that simply omitted the field would go looking for a version it does not
/// have.
///
/// Neither carries a value. `q2d_version` is the sender's own claim, and an
/// unknown one is exactly the field this build has no vocabulary for, so
/// repeating it is repeating something unparsed.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum VersionProblem {
    /// §5.2.1 `malformed`: absent, or not a string. §2.2 requires the field,
    /// and *the verified core object malformed, or missing a field §2 requires*
    /// is that row rather than this one's.
    Malformed,
    /// §5.2.1 `unsupported_version`: present, a string, and not [`SUPPORTED`].
    /// The only case in which the sender got the shape right and this build
    /// still cannot read the message.
    Unsupported,
}

impl std::fmt::Display for VersionProblem {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            VersionProblem::Malformed => f.write_str(
                "`q2d_version` is absent or is not a string — §2.2 requires it, \
                 so this is core-model.md §5.2.1's `malformed`",
            ),
            VersionProblem::Unsupported => write!(
                f,
                "`q2d_version` names a version this build does not implement; \
                 it implements {SUPPORTED} — core-model.md §4 step 5"
            ),
        }
    }
}

impl std::error::Error for VersionProblem {}

/// Whether this build interprets the verified core object.
///
/// Absent, not a string, and any other value all reject: unknown, missing and
/// indeterminate deny.
pub fn check_version(core: &Value) -> Result<(), VersionProblem> {
    let version = match core {
        Value::Object(pairs) => pairs.get("q2d_version"),
        _ => None,
    };
    match version {
        Some(Value::String(text)) if text == SUPPORTED => Ok(()),
        // A string this build does not implement. The sender got the shape
        // right, which is the one case §5.2.1 calls `unsupported_version`.
        Some(Value::String(_)) => Err(VersionProblem::Unsupported),
        // Absent, or some other type. §2.2 requires a string here, so §5.2.1's
        // `malformed` row — *missing a field §2 requires* — is the one that
        // applies, and telling a requester `unsupported_version` would send it
        // looking for a version it does not have.
        _ => Err(VersionProblem::Malformed),
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
    fn a_version_this_build_does_not_implement_is_unsupported() {
        // Unknown, missing and indeterminate all deny. A version this build
        // does not implement is not a thing to negotiate: §1 has no round trip
        // in which to negotiate it.
        for version in [
            // A version from the future, and one from a past that never was.
            "0.2", "0.0",
            // Prefixes and suffixes, which a `starts_with` or trimming check
            // would admit, and none of which is this version.
            "0.10", "0.1.0", " 0.1", "0.1 ",
        ] {
            let core = Value::object([("q2d_version", Value::string(version))]);
            assert_eq!(
                check_version(&core),
                Err(VersionProblem::Unsupported),
                "{version:?}"
            );
        }
    }

    #[test]
    fn an_absent_or_mistyped_version_is_malformed_rather_than_unsupported() {
        // §5.2.1 gives these two rows: *the verified core object malformed, or
        // missing a field §2 requires* is `malformed`, and only an unknown
        // value is `unsupported_version`. Collapsing them here would make the
        // external value unrecoverable, and a requester told
        // `unsupported_version` about a message that omitted the field would go
        // looking for a version it does not have.
        for core in [
            // The number rather than the string: §2.2's field is a string, and
            // a check that coerced would accept a shape the profile refuses.
            Value::object([("q2d_version", Value::Integer(0))]),
            Value::object([("q2d_version", Value::Null)]),
            // Absent, and not an object at all.
            Value::object([("type", Value::string("query"))]),
            Value::Null,
            Value::Array(vec![]),
        ] {
            assert_eq!(
                check_version(&core),
                Err(VersionProblem::Malformed),
                "{core:?}"
            );
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
        assert_eq!(check_version(&nonsense), Err(VersionProblem::Unsupported));

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
        let message = VersionProblem::Unsupported.to_string();
        assert!(message.contains("q2d_version"));
        assert!(message.contains(SUPPORTED));
        // And the malformed one names §2.2's requirement rather than a version.
        let malformed = VersionProblem::Malformed.to_string();
        assert!(malformed.contains("§2.2"), "{malformed}");
        assert!(!malformed.contains("does not implement"), "{malformed}");
    }
}
