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
        let effective_from = Self::date(&text(provenance, "effective_from")?, "effective_from")?;
        let revoked_from = match member(provenance, "revoked_from")? {
            Value::Null => None,
            Value::String(s) => Some(Self::date(s, "revoked_from")?),
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
        // **Exactly one of `millibits` and `table`**, and neither is optional in
        // the sense of *may be absent*. A constant capacity carries `millibits`;
        // one that depends on the public context carries `table`, which the
        // scheduling predicate's does.
        //
        // Absent-means-table is what this first did, and review found it: an
        // entry with *neither* loaded as a table capacity nobody could evaluate,
        // and an entry with *both* silently used `millibits` while a table said
        // otherwise. Both reach P-008 as a debit that is missing or wrong, which
        // is Q2D-C-09's whole subject.
        let Value::Object(fields) = capacity else {
            return Err(LoadError(format!("`{id}`'s `capacity` is not an object")));
        };
        let has_table = fields.contains_key("table");
        let capacity_millibits = match (fields.get("millibits"), has_table) {
            (Some(_), true) => {
                return Err(LoadError(format!(
                    "`{id}`'s capacity carries both `millibits` and `table`, so which \
                     one a debit comes from is undecided"
                )))
            }
            (None, false) => {
                return Err(LoadError(format!(
                    "`{id}`'s capacity carries neither `millibits` nor `table`, so \
                     nothing could be debited for it"
                )))
            }
            (None, true) => None,
            (Some(Value::Integer(n)), false) => {
                // Negative is not a small debit, it is a credit — no cardinality
                // yields one, and an entry carrying one would *return* budget on
                // every answer. Zero is legal: a domain of one value is
                // degenerate rather than malformed, and refusing it would be a
                // rule invented here.
                if *n < 0 {
                    return Err(LoadError(format!(
                        "`{id}`'s `capacity.millibits` is {n}; a negative capacity \
                         would credit the budget rather than debit it"
                    )));
                }
                Some(*n)
            }
            (Some(_), false) => {
                return Err(LoadError(format!(
                    "`{id}`'s `capacity.millibits` is not an integer; core-model.md \
                     §3.1 keeps floating point out of budget accounting"
                )))
            }
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

        // **Issue 12: the stored digest is recomputed, never trusted.** A
        // manifest whose entry says what its own digest is would be vouching for
        // itself, which is the same mistake as reading verification parameters
        // out of a protected header. `entry_digest_rule` in the manifest states
        // the rule by citation: sha256 over the entry with `entry_digest`
        // removed, serialized under `serialization.md` §1.
        //
        // Done here, while the parsed value is still in hand. Recomputing later
        // would mean either keeping every entry's `Value` alongside its typed
        // form — two representations that can disagree — or re-reading the file.
        let stored = text(value, "entry_digest")?;
        let recomputed = Self::recompute_entry_digest(value, &id)?;
        if recomputed != stored {
            return Err(LoadError(format!(
                "`{id}` version `{version}` stores entry digest {stored} and computes \
                 {recomputed}; a stored digest is data, not evidence"
            )));
        }

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
            entry_digest: stored,
        })
    }

    /// A `YYYY-MM-DD` date that is a real day.
    ///
    /// Checked at **load**, because `resolve` compares dates as text and text
    /// comparison is only exact over well-formed ones — `0000-00-00` sorts
    /// before everything and `zzzz` after it, so a malformed date in a pinned
    /// manifest would resolve rather than fail. Review found that.
    ///
    /// Validated by appending a midnight time and asking
    /// [`crate::timestamp::is_q2d_timestamp`], rather than by a second date
    /// parser here. §2.2 already decides what a real day is, and two answers to
    /// that question is one more than the protocol has.
    fn date(value: &str, field: &str) -> Result<String, LoadError> {
        if value.len() != DATE_LENGTH
            || !crate::timestamp::is_q2d_timestamp(&format!("{value}T00:00:00Z"))
        {
            return Err(LoadError(format!(
                "`provenance.{field}` is `{value}`, which is not a YYYY-MM-DD date"
            )));
        }
        Ok(value.to_string())
    }

    /// sha256 over the entry with `entry_digest` removed, serialized under
    /// `serialization.md` §1 — the manifest's own `entry_digest_rule`.
    fn recompute_entry_digest(value: &Value, id: &str) -> Result<String, LoadError> {
        let Value::Object(fields) = value else {
            return Err(LoadError(format!("`{id}` is not an object")));
        };
        let mut without = fields.clone();
        // Removed rather than blanked. A digest over an entry carrying an empty
        // `entry_digest` would be a different rule from the one the manifest
        // states, and would still be self-referential in shape.
        without.remove("entry_digest");
        let bytes = crate::value::serialize(&Value::Object(without)).map_err(|e| {
            LoadError(format!("`{id}` cannot be serialized for its digest: {e}"))
        })?;
        Ok(crate::digest::digest(&bytes))
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

/// Why resolution refused — P-005 §4.7 items 5 to 8, plus §4.5's digest.
///
/// **Not a wire value, for the reason [`crate::replay::ReplayRejection`] is
/// not.** `core-model.md` §5.2.1 gives everything from step 9 onward the value
/// the responder's **pinned registry** declares, and resolution is step 10. The
/// value is [`Manifest::denial_normalization`] — data this custodian pinned —
/// so a constant here would compile one deployment's configuration into every
/// deployment.
///
/// §4.7 requires all of these to be indistinguishable on the wire. They are told
/// apart **only** in a local audit event, which is what the separate internal
/// reasons are for.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ResolveError {
    /// No entry with this identifier, at any version.
    UnknownPredicate,
    /// The identifier is known and this version is not.
    ///
    /// Separate from [`Self::UnknownPredicate`] for the operator, and identical
    /// to it on the wire: distinguishing them would tell a requester that the
    /// predicate exists, which is exactly the custodian-private policy §4.7
    /// withholds.
    UnknownVersion,
    /// `deprecated` or `revoked` — §4.6.
    NotResolvable,
    /// `effective_from` is in the future.
    NotYetEffective,
    /// `revoked_from` has passed.
    ///
    /// Distinct from [`Self::NotResolvable`] because a manifest may carry a
    /// revocation date on an entry still marked active — the date is what
    /// governs, and an operator needs to know which of the two refused.
    RevokedByDate,
    /// The requester's `predicate.registry_digest` is not this entry's — §4.5.
    EntryDigestMismatch,
}

impl ResolveError {
    /// The corpus's name for this reason.
    pub fn internal_reason(&self) -> &'static str {
        match self {
            ResolveError::UnknownPredicate => "unknown_predicate",
            ResolveError::UnknownVersion => "unknown_predicate_version",
            ResolveError::NotResolvable => "predicate_not_resolvable",
            ResolveError::NotYetEffective => "predicate_not_yet_effective",
            ResolveError::RevokedByDate => "predicate_revoked",
            ResolveError::EntryDigestMismatch => "entry_digest_mismatch",
        }
    }

    /// `core-model.md` §4's step. Always 10.
    pub fn step(&self) -> &'static str {
        "10"
    }
}

impl Manifest {
    /// `core-model.md` §4 step 10 — P-005 §4.5 and §4.6.
    ///
    /// ## The declared digest is a parameter, not a second call
    ///
    /// §5: *"a separate comparison call could be skipped; a parameter cannot."*
    /// A caller holding an [`Entry`] has already passed the comparison, which is
    /// why [`Manifest::entry_for`] is named as a lookup and this is named as the
    /// resolution.
    ///
    /// ## Order
    ///
    /// Existence, then status, then dates, then the declared digest. The digest
    /// is last because it is the only one that depends on what the *requester*
    /// said — the others are facts about the entry, and an operator reading an
    /// audit event wants the entry's own problem named before the requester's.
    ///
    /// ## What is not here
    ///
    /// §4.7 item 9 — an entry requiring an assurance profile the responder does
    /// not support. That needs the responder's supported set, which is neither
    /// in the manifest nor in a message, and the module that knows it is the
    /// pipeline's. It shares this wire value when it lands.
    pub fn resolve(
        &self,
        id: &str,
        version: &str,
        declared_entry_digest: &str,
        now: &str,
    ) -> Result<&Entry, ResolveError> {
        let Some(entry) = self.entry_for(id, version) else {
            // Which of the two it is costs an extra lookup and is worth it: an
            // operator debugging a requester's integration needs to know whether
            // the predicate is unknown or the version is, and §4.7 makes both
            // identical on the wire regardless.
            let known = self.entries.keys().any(|(known_id, _)| known_id == id);
            return Err(if known {
                ResolveError::UnknownVersion
            } else {
                ResolveError::UnknownPredicate
            });
        };
        if !entry.status.resolvable() {
            return Err(ResolveError::NotResolvable);
        }
        // Dates compare as text, which is exact rather than convenient:
        // `YYYY-MM-DD` sorts identically as a string and as a date, and a §2.2
        // timestamp begins with exactly that. So a date is compared against the
        // date part of `now` with no parsing and no timezone question.
        let today = &now[..DATE_LENGTH.min(now.len())];
        if today < entry.effective_from.as_str() {
            return Err(ResolveError::NotYetEffective);
        }
        if let Some(revoked_from) = &entry.revoked_from {
            // On the day itself the entry is already revoked. A revocation that
            // took effect at the end of its own date would leave a day in which
            // an entry a publisher has withdrawn still answers.
            if today >= revoked_from.as_str() {
                return Err(ResolveError::RevokedByDate);
            }
        }
        if declared_entry_digest != entry.entry_digest {
            return Err(ResolveError::EntryDigestMismatch);
        }
        Ok(entry)
    }
}

/// `YYYY-MM-DD`.
const DATE_LENGTH: usize = 10;

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

    /// A one-entry manifest whose entry digest is **correct by construction**.
    ///
    /// The rule is restated here, which is a duplication worth naming: the
    /// fixture has to be valid for the tests that are about something else, and
    /// a fixture carrying a wrong digest would fail every one of them for the
    /// wrong reason.
    ///
    /// What checks the rule itself is not this. It is the **reference
    /// manifest**, whose three stored digests were authored by
    /// `registry/validate.py` in Python and now recompute in Rust and in Go —
    /// three readings of `entry_digest_rule` that have to agree.
    fn manifest_with(entry_patch: &str) -> Result<Manifest, LoadError> {
        manifest_with_revocation(entry_patch, "null")
    }

    fn manifest_with_revocation(
        entry_patch: &str,
        revoked_from: &str,
    ) -> Result<Manifest, LoadError> {
        let body = format!(
            r#"{{"id":"p","version":"0.1","status":"active",
                 "release_shape":"boolean",
                 "public_context_schema":{{}},"private_input_schema":{{}},
                 "output_schema":{{}},"answer_domain":{{}},"freshness":{{}},
                 "test_vectors":[],"assurance_profiles":["a"],
                 "sensitivity":{{"class":"low"}},
                 "provenance":{{"effective_from":"2026-01-01","revoked_from":{revoked_from}}},
                 {entry_patch}}}"#
        );
        // Digest the entry as the rule says — without `entry_digest` — then put
        // the result in and wrap it in a manifest.
        let entry = parse::parse(body.as_bytes())
            .map_err(|e| LoadError(format!("the fixture does not parse: {e}")))?;
        let digest = crate::digest::digest(&crate::value::serialize(&entry).unwrap());
        let raw = format!(
            r#"{{"capacity_unit":{{"name":"millibits"}},
                 "denial_normalization":{{"external_reason":"unavailable"}},
                 "predicates":[{}, "entry_digest":"{digest}"}}]}}"#,
            &body[..body.len() - 1]
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

    const MENU: &str = "https://q2d.dev/predicates/dietary/menu-compatible";

    #[test]
    fn a_known_entry_resolves_when_the_declared_digest_matches() {
        let manifest = reference();
        let entry = manifest
            .resolve(MENU, "0.1", DIGEST, "2026-08-31T09:00:00Z")
            .expect("resolves");
        assert_eq!(entry.id(), MENU);
    }

    #[test]
    fn a_declared_digest_that_differs_rejects() {
        // §4.5. The failure this closes is **semantic mutation without shape
        // change**: a predicate edited from *is any item compatible* to *does
        // any item conflict* keeps its release shape, domain, capacity and
        // schema, so every other check passes and the answer means the opposite
        // of what the requester believes.
        let manifest = reference();
        let wrong = "sha256:0000000000000000000000000000000000000000000000000000000000000000";
        assert_eq!(
            manifest.resolve(MENU, "0.1", wrong, "2026-08-31T09:00:00Z"),
            Err(ResolveError::EntryDigestMismatch)
        );
    }

    #[test]
    fn an_unknown_predicate_and_an_unknown_version_are_told_apart_only_locally() {
        // Two internal reasons, and §4.7 makes them one wire value: telling them
        // apart on the wire would say the predicate exists, which is the
        // custodian-private policy the uniformity rule withholds.
        let manifest = reference();
        let now = "2026-08-31T09:00:00Z";
        assert_eq!(
            manifest.resolve("https://q2d.dev/predicates/nope", "0.1", DIGEST, now),
            Err(ResolveError::UnknownPredicate)
        );
        assert_eq!(
            manifest.resolve(MENU, "9.9", DIGEST, now),
            Err(ResolveError::UnknownVersion)
        );
    }

    #[test]
    fn an_entry_that_is_not_yet_effective_rejects() {
        // The reference entries are effective from 2026-08-03, so a `now` before
        // that is the case. Text comparison on the date part, which is exact.
        let manifest = reference();
        assert_eq!(
            manifest.resolve(MENU, "0.1", DIGEST, "2026-08-02T23:59:59Z"),
            Err(ResolveError::NotYetEffective)
        );
        // And the first day it is effective resolves.
        assert!(manifest.resolve(MENU, "0.1", DIGEST, "2026-08-03T00:00:00Z").is_ok());
    }

    #[test]
    fn a_revocation_date_takes_effect_on_the_day_itself() {
        // A revocation that began at the *end* of its own date would leave a
        // whole day in which an entry the publisher has withdrawn still answers.
        //
        // Built as a fixture rather than by editing the reference manifest,
        // which is what the first version of this test did — and the digest
        // recomputation refused it, correctly: changing `revoked_from` changes
        // the entry, so the stored digest no longer describes it.
        let manifest = manifest_with_revocation(
            r#""capacity":{"unit":"millibits","millibits":1}"#,
            r#""2026-09-01""#,
        )
        .expect("parses");
        let digest = manifest.entry_for("p", "0.1").unwrap().stored_entry_digest().to_string();
        assert!(manifest.resolve("p", "0.1", &digest, "2026-08-31T23:59:59Z").is_ok());
        assert_eq!(
            manifest.resolve("p", "0.1", &digest, "2026-09-01T00:00:00Z"),
            Err(ResolveError::RevokedByDate)
        );
    }

    #[test]
    fn every_resolution_failure_shares_a_step_and_is_told_apart_internally() {
        // §4.7's uniformity, in the half this module can assert: distinct
        // internal reasons, one step, and **no wire value on the type at all**
        // — §5.2.1 makes that the pinned registry's `denial_normalization`,
        // which is why it is read from the manifest and not from a constant.
        let reasons = [
            ResolveError::UnknownPredicate,
            ResolveError::UnknownVersion,
            ResolveError::NotResolvable,
            ResolveError::NotYetEffective,
            ResolveError::RevokedByDate,
            ResolveError::EntryDigestMismatch,
        ];
        let internal: std::collections::BTreeSet<_> =
            reasons.iter().map(|r| r.internal_reason()).collect();
        assert_eq!(internal.len(), reasons.len(), "two share an internal reason");
        assert!(reasons.iter().all(|r| r.step() == "10"));
        assert_eq!(reference().denial_normalization(), "unavailable");
    }

    #[test]
    fn an_entry_edited_without_updating_its_digest_is_refused() {
        // Issue 12, and **only this half**. Recomputation catches an entry whose
        // stored digest has gone stale — an edit someone forgot to re-digest, or
        // a splice into a manifest.
        //
        // It does **not** catch a publisher who edits an entry *and* updates its
        // digest to match: that manifest is self-consistent and recomputation
        // agrees with it. What catches that is the pin — §4.1's digest over the
        // whole manifest, which a custodian changes only after reading the diff.
        // The test name said otherwise until review pointed it out.
        let raw = std::fs::read(
            std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
                .join("registry")
                .join("manifest.json"),
        )
        .unwrap();
        let tampered =
            String::from_utf8(raw).unwrap().replace(r#""release_shape": "boolean""#, r#""release_shape": "enum""#);
        let error = Manifest::parse(tampered.as_bytes()).unwrap_err();
        assert!(error.to_string().contains("stores entry digest"), "{error}");
    }

    #[test]
    fn a_malformed_date_fails_the_load() {
        // `resolve` compares dates as text, and text comparison is exact only
        // over well-formed ones: `0000-00-00` sorts before everything and `zzzz`
        // after it, so a malformed date in a pinned manifest would resolve
        // rather than fail.
        for bad in [r#""0000-00-00""#, r#""zzzz""#, r#""2026-02-30""#, r#""2026-8-3""#] {
            let error = manifest_with_revocation(
                r#""capacity":{"unit":"millibits","millibits":1}"#,
                bad,
            )
            .unwrap_err();
            assert!(error.to_string().contains("YYYY-MM-DD"), "{bad}: {error}");
        }
        // And a real date loads.
        assert!(manifest_with_revocation(
            r#""capacity":{"unit":"millibits","millibits":1}"#,
            r#""2026-02-29""#
        )
        .is_err(), "2026 is not a leap year");
        assert!(manifest_with_revocation(
            r#""capacity":{"unit":"millibits","millibits":1}"#,
            r#""2024-02-29""#
        )
        .is_ok(), "2024 is");
    }

    #[test]
    fn the_reference_manifests_stored_digests_recompute() {
        // The check on the *rule* rather than on a fixture. These three digests
        // were authored by `registry/validate.py` in Python; recomputing them
        // here is a second reading of `entry_digest_rule`, and Go's is a third.
        // A disagreement would be a specification ambiguity found.
        assert_eq!(reference().len(), 3, "all three recomputed, or parse failed");
    }

    #[test]
    fn a_capacity_must_carry_exactly_one_of_millibits_and_table() {
        // Review found both halves. Neither is a shape a publisher writes on
        // purpose, and both reach P-008 as a debit that is missing or wrong.
        let neither = manifest_with(r#""capacity":{"unit":"millibits"}"#).unwrap_err();
        assert!(neither.to_string().contains("neither"), "{neither}");
        let both = manifest_with(
            r#""capacity":{"unit":"millibits","millibits":1000,"table":{"2":1000}}"#,
        )
        .unwrap_err();
        assert!(both.to_string().contains("both"), "{both}");
        // And each alone loads.
        assert!(manifest_with(r#""capacity":{"unit":"millibits","millibits":1000}"#).is_ok());
        assert!(manifest_with(r#""capacity":{"unit":"millibits","table":{"2":1000}}"#).is_ok());
    }

    #[test]
    fn a_negative_capacity_is_refused_and_zero_is_not() {
        // A negative capacity is not a small debit, it is a credit: an entry
        // carrying one would return budget on every answer. Zero is legal — a
        // domain of one value is degenerate rather than malformed, and refusing
        // it would be a rule invented here rather than read from §3.1.
        let error =
            manifest_with(r#""capacity":{"unit":"millibits","millibits":-1000}"#).unwrap_err();
        assert!(error.to_string().contains("credit"), "{error}");
        assert!(manifest_with(r#""capacity":{"unit":"millibits","millibits":0}"#).is_ok());
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
