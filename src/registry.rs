//! The predicate registry — P-005 issues 1 and 4.
//!
//! [`RegistryPins`] is what a custodian accepted; [`Manifest`] is what it read.
//! Loading with the pins applied is issue 3 and waits on the manifest being
//! signed (issue 2); this module parses and holds, and refuses everything it
//! cannot make sense of.
//!
//! ## Parsed with this crate's own parser
//!
//! Not a general JSON library, for the reason [`crate::suites`] gives: this file
//! decides what a custodian will evaluate, so it is read by the parser that
//! refuses duplicate keys. A manifest carrying `capacity` twice is not a manifest
//! with one of them, and last-wins would let a publisher put the real value
//! second.
//!
//! ## Capacity is read, never computed
//!
//! `core-model.md` §3.1: the registry carries the millibit value precisely so
//! that implementations cannot disagree, because IEEE-754 does not guarantee a
//! correctly-rounded `log2`. [`Entry::capacity_millibits`] returns what the
//! manifest said. Nothing here calls `log2` and nothing here holds a float.

use crate::parse;
use crate::value::Value;
use std::collections::BTreeMap;
use std::fmt;

/// What a custodian has accepted — P-005 §4.1's two pins.
///
/// **Both are required, and they do different jobs.** The signing key is
/// *authentication*: the manifest came from a publisher this custodian
/// recognises. The digest is *authorization*: it is this exact content, which
/// this custodian has read. The digest is the stronger of the two, and it is
/// what makes a compromised registry key an availability problem rather than a
/// disclosure one — a new manifest signed with a stolen key does not match the
/// pin.
///
/// That property holds only while a custodian never auto-accepts a new digest,
/// which is why §4.3 forbids automatic refresh and why nothing in this module
/// fetches anything.
///
/// **There is no constructor taking a message.** The same rule as
/// [`crate::SuitePolicy`], carried by the type rather than by a comment: the
/// only way in is a list an operator wrote down.
#[derive(Debug, Clone)]
pub struct RegistryPins {
    signing_keys: Vec<[u8; 32]>,
    manifest_digest: String,
}

/// Why a manifest could not be loaded, or a pin could not be built.
///
/// **One type for both, and it is fatal to serving.** P-005 §4.2: a responder
/// that cannot verify its manifest does not serve, and there is no partial
/// success to describe — so this carries an operator-facing message and no
/// machine-readable class. A caller cannot branch on it, which is deliberate:
/// the only correct behaviour is to fail startup.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct LoadError(String);

impl fmt::Display for LoadError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.0)
    }
}

impl std::error::Error for LoadError {}

impl RegistryPins {
    /// Build from configuration.
    ///
    /// `signing_keys` are raw Ed25519 public keys and `manifest_digest` is a
    /// `sha256:`-prefixed lowercase hex string — `serialization.md` §5's form,
    /// checked here so a mistyped pin fails at startup rather than at the first
    /// comparison.
    ///
    /// An empty key list is refused. A pin set that authenticates nothing would
    /// leave the digest doing both jobs, and §4.1 requires both.
    pub fn from_config(
        signing_keys: Vec<[u8; 32]>,
        manifest_digest: &str,
    ) -> Result<Self, LoadError> {
        if signing_keys.is_empty() {
            return Err(LoadError(
                "no registry signing key is pinned, so nothing would authenticate the \
                 manifest — P-005 §4.1 requires a key pin as well as a digest pin"
                    .into(),
            ));
        }
        let hex = manifest_digest.strip_prefix("sha256:").ok_or_else(|| {
            LoadError(format!(
                "pinned manifest digest `{manifest_digest}` does not start with `sha256:` \
                 — serialization.md §5"
            ))
        })?;
        if hex.len() != 64 || !hex.bytes().all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
        {
            return Err(LoadError(format!(
                "pinned manifest digest `{manifest_digest}` is not 64 lowercase hex \
                 characters — serialization.md §5 fixes the case, so an upper-case pin \
                 would never match a computed digest"
            )));
        }
        Ok(RegistryPins {
            signing_keys,
            manifest_digest: manifest_digest.to_string(),
        })
    }

    /// The pinned digest, for the comparison issue 3 will make.
    pub fn manifest_digest(&self) -> &str {
        &self.manifest_digest
    }

    /// Whether this key is pinned.
    ///
    /// A membership question rather than an accessor returning the list: a
    /// caller that could read the keys could log them, and while a public key is
    /// not secret, *which* publishers a custodian recognises is closer to its
    /// local policy than to anything a requester should be able to learn.
    pub fn accepts_key(&self, key: &[u8; 32]) -> bool {
        self.signing_keys.contains(key)
    }

    /// How many keys are pinned, for operator tooling and tests.
    pub fn key_count(&self) -> usize {
        self.signing_keys.len()
    }
}

/// What a registry says may be done with a predicate — P-005 §4.6.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum EntryStatus {
    Active,
    Deprecated,
    Revoked,
}

impl EntryStatus {
    /// Whether a new request may resolve to this entry.
    ///
    /// **`deprecated` rejects here, unlike a deprecated cryptographic suite.**
    /// The asymmetry is not an inconsistency: a suite must keep verifying
    /// because receipts signed under it remain evidence, and a predicate is
    /// evaluated fresh on every request, so there is no old exchange to keep
    /// readable. §4.6 — deprecated and revoked differ only in what an operator
    /// is being told about intent.
    pub fn resolvable(&self) -> bool {
        matches!(self, EntryStatus::Active)
    }
}

/// One predicate definition.
///
/// Fields are private and the only origin is [`Manifest::entries`], for the
/// reason [`crate::suites::SuiteEntry`]'s are: a caller able to write
/// `Entry { status: Active, .. }` could resolve a revoked predicate, which is
/// the check restated rather than enforced.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Entry {
    id: String,
    version: String,
    status: EntryStatus,
    release_shape: String,
    capacity_millibits: Option<i64>,
    sensitivity: String,
    effective_from: String,
    revoked_from: Option<String>,
    assurance_profiles: Vec<String>,
    entry_digest: String,
}

impl Entry {
    pub fn id(&self) -> &str {
        &self.id
    }
    pub fn version(&self) -> &str {
        &self.version
    }
    pub fn status(&self) -> EntryStatus {
        self.status
    }
    pub fn release_shape(&self) -> &str {
        &self.release_shape
    }
    pub fn sensitivity(&self) -> &str {
        &self.sensitivity
    }
    pub fn effective_from(&self) -> &str {
        &self.effective_from
    }
    pub fn revoked_from(&self) -> Option<&str> {
        self.revoked_from.as_deref()
    }
    pub fn assurance_profiles(&self) -> &[String] {
        &self.assurance_profiles
    }
    /// The digest of this entry as the manifest stored it.
    ///
    /// **Stored, not verified.** Issue 12 recomputes it and refuses a manifest
    /// where any is wrong; until that lands this is what the publisher claimed,
    /// and the accessor is named to keep that distinction visible at every call
    /// site rather than only here.
    pub fn stored_entry_digest(&self) -> &str {
        &self.entry_digest
    }

    /// The entry's disclosure capacity in **integer millibits**, where it has a
    /// single value.
    ///
    /// `None` where the entry's capacity is a table rather than a constant — the
    /// scheduling predicate's depends on how many candidates the public context
    /// carries. That is [P-008](../docs/prds/P-008-capacity-accounting.md)'s to
    /// evaluate; this module reports which kind the entry has and computes
    /// nothing.
    ///
    /// Integer, and read rather than derived. `core-model.md` §3.1 keeps the
    /// value in the registry precisely because IEEE-754 does not guarantee a
    /// correctly-rounded `log2`, so two implementations computing it could
    /// disagree by a millibit.
    pub fn capacity_millibits(&self) -> Option<i64> {
        self.capacity_millibits
    }
}

/// A parsed manifest.
#[derive(Debug, Clone)]
pub struct Manifest {
    entries: BTreeMap<(String, String), Entry>,
    capacity_unit: String,
    denial_normalization: String,
}

fn member<'a>(value: &'a Value, name: &str) -> Result<&'a Value, LoadError> {
    match value {
        Value::Object(fields) => fields
            .get(name)
            .ok_or_else(|| LoadError(format!("no `{name}` in the manifest"))),
        _ => Err(LoadError(format!("`{name}` is not inside an object"))),
    }
}

fn text(value: &Value, name: &str) -> Result<String, LoadError> {
    match member(value, name)? {
        Value::String(s) => Ok(s.clone()),
        _ => Err(LoadError(format!("`{name}` is not a string"))),
    }
}

impl Manifest {
    /// Parse a manifest's bytes.
    ///
    /// **This does not verify anything.** The signature and digest checks are
    /// issue 3's `load_manifest`, and calling this directly is what a test does;
    /// a responder does not. Named `parse` rather than `load` so the difference
    /// is visible at the call site.
    pub fn parse(raw: &[u8]) -> Result<Self, LoadError> {
        let document = parse::parse(raw)
            .map_err(|e| LoadError(format!("the manifest does not parse: {e}")))?;

        // Read before the entries, because they are what a rejection built from
        // this manifest will use, and a manifest missing them is one no
        // conforming response can be built from.
        // Both are objects carrying their prose alongside the value, so the
        // value is a member rather than the field itself — `capacity_unit.name`
        // and `denial_normalization.external_reason`. Read from the document
        // rather than assumed: the first version of this reader took both for
        // strings and every reference-manifest test failed at once, which is the
        // cheap way to find out.
        let capacity_unit = text(member(&document, "capacity_unit")?, "name")?;
        let denial_normalization =
            text(member(&document, "denial_normalization")?, "external_reason")?;
        if capacity_unit != "millibits" {
            // Not a style preference. `core-model.md` §3.1 fixes the unit, and a
            // manifest declaring another one is either a different protocol or a
            // mistake; guessing which is how a capacity in bits gets debited as
            // millibits.
            return Err(LoadError(format!(
                "`capacity_unit` is `{capacity_unit}`; core-model.md §3.1 fixes it as \
                 `millibits`"
            )));
        }

        let listed = member(&document, "predicates")?;
        let Value::Array(predicates) = listed else {
            return Err(LoadError("`predicates` is not an array".into()));
        };

        let mut entries = BTreeMap::new();
        for predicate in predicates {
            let entry = Self::entry(predicate)?;
            let key = (entry.id.clone(), entry.version.clone());
            // One identifier and version means one definition. Two would make a
            // resolution ambiguous in exactly the field a requester pins.
            if entries.contains_key(&key) {
                return Err(LoadError(format!(
                    "`{}` version `{}` appears twice",
                    key.0, key.1
                )));
            }
            entries.insert(key, entry);
        }
        if entries.is_empty() {
            return Err(LoadError(
                "the manifest has no predicates, so nothing could resolve".into(),
            ));
        }
        Ok(Manifest {
            entries,
            capacity_unit,
            denial_normalization,
        })
    }

    fn entry(value: &Value) -> Result<Entry, LoadError> {
        let id = text(value, "id")?;
        let version = text(value, "version")?;
        let declared = text(value, "status")?;
        let status = match declared.as_str() {
            "active" => EntryStatus::Active,
            "deprecated" => EntryStatus::Deprecated,
            "revoked" => EntryStatus::Revoked,
            // Fail-closed. A status this build does not understand is one whose
            // rules it cannot apply, and defaulting to active is how a revoked
            // predicate becomes resolvable.
            other => {
                return Err(LoadError(format!(
                    "`{other}` is not a status P-005 §4.6 defines"
                )))
            }
        };

        // Every field `terminology.md` §3 gives a registry entry must be present,
        // not only the ones this type reads. A manifest missing `output_schema`
        // is one whose author did not fill in the shape, and reading it for the
        // parts that happen to be there is how a half-written entry reaches
        // evaluation.
        for required in [
            "public_context_schema",
            "private_input_schema",
            "output_schema",
            "answer_domain",
            "freshness",
            "test_vectors",
        ] {
            member(value, required)?;
        }

        let provenance = member(value, "provenance")?;
        let effective_from = text(provenance, "effective_from")?;
        let revoked_from = match member(provenance, "revoked_from")? {
            Value::Null => None,
            Value::String(s) => Some(s.clone()),
            _ => {
                return Err(LoadError(
                    "`provenance.revoked_from` is neither a date nor null".into(),
                ))
            }
        };

        let capacity = member(value, "capacity")?;
        let unit = text(capacity, "unit")?;
        if unit != "millibits" {
            return Err(LoadError(format!(
                "`{id}`'s capacity is in `{unit}`; core-model.md §3.1 fixes millibits"
            )));
        }
        // Absent where the entry's capacity is a table rather than a constant,
        // which the scheduling predicate's is. Present-and-not-an-integer is a
        // different thing and is refused: a float here is the arithmetic §3.1
        // keeps out of budget accounting.
        let capacity_millibits = match capacity {
            Value::Object(fields) => match fields.get("millibits") {
                None => None,
                Some(Value::Integer(n)) => Some(*n),
                Some(_) => {
                    return Err(LoadError(format!(
                        "`{id}`'s `capacity.millibits` is not an integer; core-model.md \
                         §3.1 keeps floating point out of budget accounting"
                    )))
                }
            },
            _ => return Err(LoadError(format!("`{id}`'s `capacity` is not an object"))),
        };

        let assurance_profiles = match member(value, "assurance_profiles")? {
            Value::Array(items) => items
                .iter()
                .map(|item| match item {
                    Value::String(s) => Ok(s.clone()),
                    _ => Err(LoadError("an assurance profile is not a string".into())),
                })
                .collect::<Result<Vec<_>, _>>()?,
            _ => return Err(LoadError("`assurance_profiles` is not an array".into())),
        };

        Ok(Entry {
            id,
            version,
            status,
            release_shape: text(value, "release_shape")?,
            capacity_millibits,
            // `sensitivity.class`, not `sensitivity` — the field carries its
            // rationale alongside the class, and the rationale is for a human.
            sensitivity: text(member(value, "sensitivity")?, "class")?,
            effective_from,
            revoked_from,
            assurance_profiles,
            entry_digest: text(value, "entry_digest")?,
        })
    }

    /// Look an entry up by identifier and version.
    ///
    /// **Not `resolve`.** This is a map lookup; §4.6's status and effective-date
    /// rules and §4.5's declared-digest comparison are issue 5's and issue 7's,
    /// and a caller reaching this directly has skipped them. The name is the
    /// warning.
    pub fn entry_for(&self, id: &str, version: &str) -> Option<&Entry> {
        self.entries.get(&(id.to_string(), version.to_string()))
    }

    /// The normalized external value this registry declares — `core-model.md`
    /// §5.2.1.
    ///
    /// Every rejection from step 9 onward uses it, and it is **the registry's
    /// and not a resolved entry's**, which is what makes it available in the
    /// cases that need it most: an unknown predicate never resolves an entry.
    pub fn denial_normalization(&self) -> &str {
        &self.denial_normalization
    }

    /// The unit capacities are stated in. Always `millibits`; a manifest saying
    /// otherwise does not parse.
    pub fn capacity_unit(&self) -> &str {
        &self.capacity_unit
    }

    /// Every `(id, version)` pair, sorted. For operator tooling and tests.
    ///
    /// **Never for building a rejection.** §4.7: all nine resolution failures
    /// share one wire response, because a requester must not learn which
    /// predicates a custodian supports.
    pub fn identifiers(&self) -> Vec<(&str, &str)> {
        self.entries
            .keys()
            .map(|(id, version)| (id.as_str(), version.as_str()))
            .collect()
    }

    pub fn len(&self) -> usize {
        self.entries.len()
    }

    pub fn is_empty(&self) -> bool {
        self.entries.is_empty()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const DIGEST: &str = "sha256:bd08ff230de0d8ce34de99967f7a9097988b49058f0a21dd35b9444c24098e35";

    fn reference() -> Manifest {
        let raw = std::fs::read(
            std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
                .join("registry")
                .join("manifest.json"),
        )
        .expect("registry/manifest.json");
        Manifest::parse(&raw).expect("the reference manifest parses")
    }

    #[test]
    fn the_reference_manifest_parses() {
        let manifest = reference();
        assert_eq!(manifest.len(), 3);
        assert_eq!(manifest.capacity_unit(), "millibits");
        assert_eq!(manifest.denial_normalization(), "unavailable");
    }

    #[test]
    fn an_entry_reports_what_the_manifest_said() {
        let manifest = reference();
        let entry = manifest
            .entry_for("https://q2d.dev/predicates/dietary/menu-compatible", "0.1")
            .expect("present");
        assert_eq!(entry.status(), EntryStatus::Active);
        assert_eq!(entry.release_shape(), "boolean");
        assert_eq!(entry.capacity_millibits(), Some(1000));
        assert_eq!(entry.stored_entry_digest(), DIGEST);
        assert!(entry.revoked_from().is_none());
    }

    #[test]
    fn a_table_capacity_reports_no_single_value() {
        // The scheduling predicate's capacity depends on how many candidates the
        // public context carries, so there is no constant to report. `None` is
        // the honest answer and P-008 evaluates the table; a zero here would be
        // a debit of nothing.
        let manifest = reference();
        let entry = manifest
            .entry_for(
                "https://q2d.dev/predicates/scheduling/availability-window",
                "0.1",
            )
            .expect("present");
        assert_eq!(entry.capacity_millibits(), None);
    }

    #[test]
    fn version_is_part_of_the_key() {
        let manifest = reference();
        assert!(manifest
            .entry_for("https://q2d.dev/predicates/dietary/menu-compatible", "0.2")
            .is_none());
    }

    #[test]
    fn deprecated_does_not_resolve_where_a_deprecated_suite_would_verify() {
        // §4.6's asymmetry, asserted rather than described. A suite keeps
        // verifying because receipts signed under it remain evidence; a
        // predicate is evaluated fresh every time, so there is no old exchange
        // to keep readable.
        assert!(EntryStatus::Active.resolvable());
        assert!(!EntryStatus::Deprecated.resolvable());
        assert!(!EntryStatus::Revoked.resolvable());
        assert!(crate::suites::SuiteStatus::Deprecated.may_verify());
    }

    fn manifest_with(entry_patch: &str) -> Result<Manifest, LoadError> {
        let raw = format!(
            r#"{{"capacity_unit":{{"name":"millibits"}},
                 "denial_normalization":{{"external_reason":"unavailable"}},
                 "predicates":[{{"id":"p","version":"0.1","status":"active",
                 "release_shape":"boolean",
                 "public_context_schema":{{}},"private_input_schema":{{}},
                 "output_schema":{{}},"answer_domain":{{}},"freshness":{{}},
                 "test_vectors":[],"assurance_profiles":["a"],
                 "sensitivity":{{"class":"low"}},
                 "provenance":{{"effective_from":"2026-01-01","revoked_from":null}},
                 "entry_digest":"sha256:aa",{entry_patch}}}]}}"#
        );
        Manifest::parse(raw.as_bytes())
    }

    #[test]
    fn a_capacity_that_is_not_an_integer_is_refused() {
        // §3.1 keeps floating point out of budget accounting, and a manifest is
        // where one would enter.
        let error = manifest_with(r#""capacity":{"unit":"millibits","millibits":1000.5}"#)
            .unwrap_err();
        assert!(error.to_string().contains("integer"), "{error}");
    }

    #[test]
    fn a_capacity_in_another_unit_is_refused() {
        // Guessing is how a capacity in bits gets debited as millibits.
        assert!(manifest_with(r#""capacity":{"unit":"bits","millibits":1}"#).is_err());
    }

    #[test]
    fn an_unknown_status_fails_the_load() {
        let error = manifest_with(r#""capacity":{"unit":"millibits","millibits":1}"#)
            .map(|_| ())
            .and_then(|_| {
                Manifest::parse(
                    br#"{"capacity_unit":{"name":"millibits"},
                        "denial_normalization":{"external_reason":"u"},
                        "predicates":[{"id":"p","version":"0.1","status":"retired"}]}"#,
                )
                .map(|_| ())
            })
            .unwrap_err();
        assert!(error.to_string().contains("retired"), "{error}");
    }

    #[test]
    fn a_missing_schema_field_fails_the_load() {
        // Read for the parts that happen to be there is how a half-written entry
        // reaches evaluation.
        // Every other required field present, so this proves `output_schema`
        // specifically is required rather than proving the loop runs at all.
        let raw = br#"{"capacity_unit":{"name":"millibits"},
            "denial_normalization":{"external_reason":"u"},
            "predicates":[{"id":"p","version":"0.1","status":"active",
            "release_shape":"boolean","sensitivity":{"class":"low"},
            "entry_digest":"sha256:aa","public_context_schema":{},
            "private_input_schema":{},"answer_domain":{},"freshness":{},
            "test_vectors":[],
            "capacity":{"unit":"millibits","millibits":1},"assurance_profiles":[],
            "provenance":{"effective_from":"2026-01-01","revoked_from":null}}]}"#;
        let error = Manifest::parse(raw).unwrap_err();
        assert!(error.to_string().contains("output_schema"), "{error}");
    }

    #[test]
    fn a_duplicate_key_in_the_manifest_fails_the_load() {
        // The reason this uses the crate's own parser: last-wins would let a
        // publisher put the real value second.
        let raw = br#"{"capacity_unit":{"name":"millibits"},
            "capacity_unit":{"name":"bits"},
            "denial_normalization":{"external_reason":"u"},"predicates":[]}"#;
        assert!(Manifest::parse(raw).is_err());
    }

    #[test]
    fn pins_require_a_key_and_a_well_formed_digest() {
        assert!(RegistryPins::from_config(vec![[0u8; 32]], DIGEST).is_ok());
        // No key: the digest would be doing both of §4.1's jobs.
        assert!(RegistryPins::from_config(vec![], DIGEST).is_err());
        for bad in [
            "bd08ff230de0d8ce34de99967f7a9097988b49058f0a21dd35b9444c24098e35",
            "sha256:BD08FF230DE0D8CE34DE99967F7A9097988B49058F0A21DD35B9444C24098E35",
            "sha256:tooshort",
            "sha512:bd08ff230de0d8ce34de99967f7a9097988b49058f0a21dd35b9444c24098e35",
        ] {
            assert!(
                RegistryPins::from_config(vec![[0u8; 32]], bad).is_err(),
                "{bad}"
            );
        }
    }

    #[test]
    fn a_key_is_asked_about_rather_than_listed() {
        // Which publishers a custodian recognises is closer to local policy than
        // to anything a requester should learn, so the type answers a membership
        // question and does not hand the list back.
        let pins = RegistryPins::from_config(vec![[7u8; 32]], DIGEST).unwrap();
        assert!(pins.accepts_key(&[7u8; 32]));
        assert!(!pins.accepts_key(&[8u8; 32]));
        assert_eq!(pins.key_count(), 1);
    }

    #[test]
    fn nothing_builds_pins_from_a_message() {
        // Asserted by the interface rather than by a runtime check: the only
        // constructor takes a key list and a digest an operator wrote down, and
        // no function in this crate produces either from received bytes. This
        // test names the property so the next person adding a constructor reads
        // it.
        let pins = RegistryPins::from_config(vec![[1u8; 32]], DIGEST).unwrap();
        assert_eq!(pins.manifest_digest(), DIGEST);
    }
}
