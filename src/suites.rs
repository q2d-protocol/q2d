//! The suite registry, loaded from a file rather than compiled in.
//!
//! P-003 issue 3. [`crypto-suites.md`](https://github.com/q2d-protocol/q2d/blob/main/spec/crypto-suites.md)
//! §2 fixes the entry fields and §6 the status rules; this module reads them.
//!
//! ## Why a file, for one entry
//!
//! Adding a second suite becomes a data change rather than a code change in two
//! languages — and, more to the point, the pinning and status-checking paths
//! run from the first day instead of being retrofitted when they matter. **A
//! pinning path that has never run is a pinning path that does not work.**
//!
//! ## Presence is not acceptance
//!
//! Resolving a suite here says the protocol knows it and what its status is. It
//! does **not** say a verifier will accept it: that is [`crate::policy`], which
//! is local configuration and is never derived from a message. The two are
//! separate types so that a caller cannot use one where it needs the other —
//! §4.2 step 2 is the whole downgrade defence and it reads the policy, not this.
//!
//! ## Status is read, never assumed
//!
//! [`SuiteStatus`] is parsed from the file and an unrecognized value is a load
//! failure rather than a default. A registry naming a status this build does
//! not understand is one whose rules this build cannot apply, and guessing is
//! how a `withdrawn` suite gets treated as usable.

use crate::parse::{parse, ParseError};
use crate::value::Value;
use std::collections::BTreeMap;
use std::fmt;

/// What a registry says may be done with a suite — `crypto-suites.md` §6.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SuiteStatus {
    Active,
    Deprecated,
    Withdrawn,
}

impl SuiteStatus {
    /// May a producer sign under this suite?
    ///
    /// The asymmetry with [`Self::may_verify`] is the point: a deprecated suite
    /// still verifies because receipts signed under it remain evidence.
    pub fn may_produce(self) -> bool {
        matches!(self, SuiteStatus::Active)
    }

    /// May a verifier accept a signature under this suite?
    pub fn may_verify(self) -> bool {
        matches!(self, SuiteStatus::Active | SuiteStatus::Deprecated)
    }
}

/// One registry entry.
#[derive(Debug, Clone)]
pub struct SuiteEntry {
    pub id: String,
    pub algorithm: String,
    pub serialization: String,
    pub hash: String,
    pub status: SuiteStatus,
}

/// A loaded registry.
#[derive(Debug, Clone)]
pub struct SuiteRegistry {
    entries: BTreeMap<String, SuiteEntry>,
}

/// Why a registry did not load, or a suite did not resolve.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RegistryError(String);

impl fmt::Display for RegistryError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.0)
    }
}

impl std::error::Error for RegistryError {}

impl From<ParseError> for RegistryError {
    fn from(error: ParseError) -> Self {
        RegistryError(format!("the suite registry does not parse: {error}"))
    }
}

fn member<'a>(object: &'a Value, name: &str) -> Result<&'a Value, RegistryError> {
    match object {
        Value::Object(members) => members
            .get(name)
            .ok_or_else(|| RegistryError(format!("no `{name}` in the suite registry"))),
        _ => Err(RegistryError(format!("`{name}` is not inside an object"))),
    }
}

fn text(value: &Value, name: &str) -> Result<String, RegistryError> {
    match value {
        Value::String(s) => Ok(s.clone()),
        _ => Err(RegistryError(format!("`{name}` is not a string"))),
    }
}

impl SuiteRegistry {
    /// Load a registry from its bytes.
    ///
    /// Parsed with [`crate::parse`], not a JSON library: this file decides which
    /// algorithms a verifier accepts, so it is read by the parser that refuses
    /// duplicate keys rather than one that resolves them by last-wins. A
    /// registry with `status` twice is not a registry with one of them.
    pub fn load(bytes: &[u8]) -> Result<Self, RegistryError> {
        let document = parse(bytes)?;
        let suites = match member(&document, "suites")? {
            Value::Array(items) => items.clone(),
            _ => return Err(RegistryError("`suites` is not an array".into())),
        };

        let mut entries = BTreeMap::new();
        for suite in &suites {
            let id = text(member(suite, "id")?, "id")?;
            let status = match text(member(suite, "status")?, "status")?.as_str() {
                "active" => SuiteStatus::Active,
                "deprecated" => SuiteStatus::Deprecated,
                "withdrawn" => SuiteStatus::Withdrawn,
                // Fail-closed. A status this build does not understand is one
                // whose rules it cannot apply, and defaulting to `active` is
                // how a withdrawn suite becomes usable.
                other => {
                    return Err(RegistryError(format!(
                        "`{other}` is not a status `crypto-suites.md` §6 defines"
                    )))
                }
            };
            let entry = SuiteEntry {
                id: id.clone(),
                algorithm: text(member(suite, "algorithm")?, "algorithm")?,
                serialization: text(member(suite, "serialization")?, "serialization")?,
                hash: text(member(suite, "hash")?, "hash")?,
                status,
            };
            // A registry naming one identifier twice is ambiguous about that
            // suite's status, which is the field the whole file exists to
            // carry. `parse` refuses duplicate *keys*; two array elements with
            // the same `id` are a different shape and are refused here.
            if entries.insert(id.clone(), entry).is_some() {
                return Err(RegistryError(format!(
                    "`{id}` is registered twice, so its status is ambiguous"
                )));
            }
        }

        if entries.is_empty() {
            return Err(RegistryError(
                "the suite registry is empty, so nothing could verify".into(),
            ));
        }
        Ok(SuiteRegistry { entries })
    }

    /// Load a registry whose digest a verifier has pinned.
    ///
    /// **The digest is checked before the bytes are parsed**, which is the same
    /// ordering `core-model.md` §4 applies to a signature: an unpinned file is
    /// attacker-controlled input, and parsing it first would run this module's
    /// parser over bytes nobody vouched for to learn something the digest
    /// already decided.
    ///
    /// A mismatch is fatal to startup rather than a warning. §4.3's reason is
    /// that a file deciding which algorithms a verifier accepts is the last one
    /// that should be unauthenticated — and a warning on that file is a
    /// deployment that runs on whatever it was handed.
    ///
    /// The registry itself is **unsigned** today, exactly as
    /// `registry/manifest.json` is; the signature is P-005's to build and the
    /// pinning is here so that the path exists before it is load-bearing.
    pub fn load_pinned(bytes: &[u8], expected: &str) -> Result<Self, RegistryError> {
        let actual = crate::digest(bytes);
        if actual != expected {
            // Neither digest is secret — one is configuration and the other is
            // computed from a file the operator holds — and an operator with a
            // mismatch needs both to tell which of the two is stale.
            return Err(RegistryError(format!(
                "suite registry digest is {actual}, and {expected} was pinned"
            )));
        }
        Self::load(bytes)
    }

    /// Resolve an identifier to its entry.
    ///
    /// Status-aware in the sense that the entry carries its status; it is **not**
    /// a policy check. A caller deciding whether to verify asks the entry and
    /// the policy, in that order, and both must say yes.
    pub fn resolve(&self, id: &str) -> Result<&SuiteEntry, RegistryError> {
        self.entries.get(id).ok_or_else(|| {
            // The identifier is echoed because it came from a message and is
            // already known to the sender. What is never echoed is which suites
            // *are* registered — §4.5, and the reason rejection names no
            // alternative.
            RegistryError(format!("`{id}` is not a registered suite"))
        })
    }

    /// Every registered identifier, for operator tooling and tests.
    ///
    /// Not for building a rejection message. §4.5: a rejection names no
    /// alternative, because suggesting one turns every rejection into a probe
    /// of local policy.
    pub fn identifiers(&self) -> Vec<&str> {
        self.entries.keys().map(String::as_str).collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn reference() -> SuiteRegistry {
        let path = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
            .join("registry")
            .join("suites.json");
        SuiteRegistry::load(&std::fs::read(path).expect("registry/suites.json"))
            .expect("the reference registry loads")
    }

    #[test]
    fn the_reference_registry_loads_and_carries_the_mandatory_suite() {
        let registry = reference();
        let entry = registry.resolve("eddsa-jws-2026").expect("registered");
        assert_eq!(entry.status, SuiteStatus::Active);
        assert!(entry.algorithm.contains("Ed25519"));
    }

    #[test]
    fn status_comes_from_the_file() {
        // The acceptance for this issue: change the file, and behaviour changes
        // without touching code. A compiled-in table would pass every other
        // test in this module.
        let deprecated = r#"{"suites":[{"id":"x","algorithm":"a","serialization":"s",
            "hash":"h","status":"deprecated"}]}"#;
        let registry = SuiteRegistry::load(deprecated.as_bytes()).unwrap();
        let entry = registry.resolve("x").unwrap();
        assert!(!entry.status.may_produce());
        assert!(entry.status.may_verify());
    }

    #[test]
    fn the_three_statuses_differ_in_the_way_section_6_says() {
        assert!(SuiteStatus::Active.may_produce() && SuiteStatus::Active.may_verify());
        // Deprecated is the asymmetric one, and the asymmetry is the point.
        assert!(!SuiteStatus::Deprecated.may_produce() && SuiteStatus::Deprecated.may_verify());
        assert!(!SuiteStatus::Withdrawn.may_produce() && !SuiteStatus::Withdrawn.may_verify());
    }

    #[test]
    fn an_unknown_status_fails_the_load() {
        // Fail-closed: not a default, and not ignored. A registry this build
        // cannot read the rules of is one it must not act on.
        let text = r#"{"suites":[{"id":"x","algorithm":"a","serialization":"s",
            "hash":"h","status":"provisional"}]}"#;
        let error = SuiteRegistry::load(text.as_bytes()).unwrap_err();
        assert!(error.to_string().contains("provisional"), "{error}");
    }

    #[test]
    fn a_duplicate_identifier_fails_the_load() {
        let text = r#"{"suites":[
            {"id":"x","algorithm":"a","serialization":"s","hash":"h","status":"active"},
            {"id":"x","algorithm":"a","serialization":"s","hash":"h","status":"withdrawn"}]}"#;
        let error = SuiteRegistry::load(text.as_bytes()).unwrap_err();
        assert!(error.to_string().contains("twice"), "{error}");
    }

    #[test]
    fn a_duplicate_key_fails_the_load() {
        // Because this reads with `parse` rather than a permissive library. A
        // registry with `status` twice is not a registry with one of them, and
        // last-wins would let the second copy decide what a verifier accepts.
        let text = r#"{"suites":[{"id":"x","algorithm":"a","serialization":"s",
            "hash":"h","status":"withdrawn","status":"active"}]}"#;
        assert!(SuiteRegistry::load(text.as_bytes()).is_err());
    }

    #[test]
    fn an_empty_registry_fails_the_load() {
        // A registry with no entries verifies nothing, so loading one silently
        // would turn a distribution failure into a total outage with no error.
        assert!(SuiteRegistry::load(br#"{"suites":[]}"#).is_err());
    }

    #[test]
    fn a_missing_field_fails_the_load() {
        for missing in ["id", "algorithm", "serialization", "hash", "status"] {
            let mut fields: Vec<String> = ["id", "algorithm", "serialization", "hash", "status"]
                .iter()
                .filter(|f| **f != missing)
                .map(|f| format!(r#""{f}":"{}""#, if *f == "status" { "active" } else { "x" }))
                .collect();
            fields.sort();
            let text = format!(r#"{{"suites":[{{{}}}]}}"#, fields.join(","));
            assert!(
                SuiteRegistry::load(text.as_bytes()).is_err(),
                "a registry without `{missing}` loaded"
            );
        }
    }

    #[test]
    fn a_pinned_digest_must_match() {
        let bytes = br#"{"suites":[{"id":"x","algorithm":"a","serialization":"s",
            "hash":"h","status":"active"}]}"#;
        let digest = crate::digest(bytes);
        assert!(SuiteRegistry::load_pinned(bytes, &digest).is_ok());

        let wrong = "sha256:0000000000000000000000000000000000000000000000000000000000000000";
        let error = SuiteRegistry::load_pinned(bytes, wrong).unwrap_err();
        assert!(error.to_string().contains(&digest), "{error}");
        assert!(error.to_string().contains(wrong), "{error}");
    }

    #[test]
    fn the_digest_is_checked_before_the_bytes_are_parsed() {
        // Bytes that are not JSON at all. If the digest were checked second,
        // this would fail with a parse error — telling an operator that a file
        // they never pinned is malformed, which is a fact about attacker input
        // and not about their configuration.
        let error = SuiteRegistry::load_pinned(b"not json", "sha256:whatever").unwrap_err();
        assert!(error.to_string().contains("pinned"), "{error}");
        assert!(!error.to_string().contains("parse"), "{error}");
    }

    #[test]
    fn an_unregistered_suite_does_not_resolve() {
        let error = reference().resolve("hmac-sha1-1999").unwrap_err();
        // The identifier is echoed — it came from the sender. What must not
        // appear is any other suite's name.
        assert!(error.to_string().contains("hmac-sha1-1999"));
        assert!(!error.to_string().contains("eddsa"), "{error}");
    }
}
