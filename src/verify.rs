//! §4.2's four-step sequence — P-003 issues 6, 7 and 12.
//!
//! ```text
//! 1. Read the declared suite from the protected header's `suite` member.
//! 2. Reject unless it is a member of the verifier's own acceptable set.
//! 3. Verify using the parameters of the registry entry for that suite —
//!    never parameters taken from the header.
//! 4. After verification, confirm the payload's `signature.profile` equals the
//!    header's `suite`, and `signature.key_id` equals the header's `key_id`.
//! ```
//!
//! **Step 2 is the whole defence.** A verifier that verifies with whatever the
//! header names has agility in the same sense that an unlocked door has a lock.
//! The acceptable set is [`crate::SuitePolicy`], which is local configuration
//! and has no constructor taking a message.
//!
//! **Step 4 is not redundant**, though both header and payload are covered by
//! the signature so neither can be altered without detection. It catches a
//! *producer* that signs a payload declaring one suite using a header declaring
//! another — a real implementation bug that no verifier would otherwise notice,
//! and the same for the key. Two comparisons, not one: a producer signing with
//! one key while the header names another is worse, because the verifier
//! resolved and used the header's key, so the signature verifies and nothing
//! downstream knows the signed object disagrees about who signed it.
//!
//! ## What the header may not decide
//!
//! Nothing. It **declares**; local policy and the registry **decide**. A header
//! carrying any member beyond `suite` and `key_id` is rejected before the suite
//! is even looked up — including one carrying parameters that would weaken
//! verification, which is P-003 issue 12's case. There is no code path that
//! reads a verification parameter from a header, so that vector is refused by
//! the closed member set rather than by a rule about the parameters it carries.

use crate::base64url;
use crate::ed25519::SignatureInvalid;
use crate::jws;
use crate::keys::KeyResolver;
use crate::policy::SuitePolicy;
use crate::suites::SuiteRegistry;
use crate::value::Value;
use std::fmt;

/// Why a message was rejected, as a responder records it locally.
///
/// **This is the internal reason and never the wire response.** They are
/// separate values (`core-model.md` §5.2), and P-009 builds the response from
/// [`Self::external_reason`] rather than from this type's name.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Rejected {
    /// `signed` is not three segments.
    CompactSegmentCount,
    /// A segment is not base64url. One variant per segment, because an operator
    /// debugging this needs to know which — and because the corpus asserts the
    /// internal reason, so two causes sharing one would make two vectors
    /// indistinguishable in the half that is meant to distinguish them.
    HeaderSegmentNotBase64url,
    PayloadSegmentNotBase64url,
    SignatureSegmentNotBase64url,
    /// The header decoded and is not an object.
    HeaderNotAnObject,
    /// The header is an object and a member is not a string.
    HeaderMemberNotAString,
    /// The header carries a member §3 does not permit.
    HeaderMemberNotPermitted,
    /// The suite is not in the registry at all.
    ///
    /// **Three variants, one wire value**, and §5.2.1 names *two causes* — the
    /// suite unregistered, or below the verifier's minimum acceptable policy.
    /// This is not a third cause. A withdrawn suite is below **every**
    /// conforming verifier's acceptable policy, because `crypto-suites.md` §6
    /// requires verification to stop accepting it; the second cause already
    /// covers it, and nothing here adds to §5.2.1's table.
    ///
    /// What is split is the **internal reason**, which §5.2 makes a separate
    /// value from the wire response precisely so it can be finer. The registry
    /// withdrawing a suite binds every deployment; an acceptable set is local.
    /// An operator needs to know which of those refused a message, and a
    /// requester must not — separating them on the wire would say whether the
    /// custodian *knows* a suite it declined, which is its minimum acceptable
    /// policy.
    SuiteUnregistered,
    /// Registered, and its status forbids verifying — `crypto-suites.md` §6's
    /// `withdrawn`.
    ///
    /// Distinct from [`Self::SuiteBelowPolicy`] because they are different
    /// facts for an operator, and different facts for the corpus: one is *the
    /// registry retired this suite*, which every deployment must honour, the
    /// other *this deployment does not accept it*, which is local. A vector
    /// asserting §6's withdrawal rule cannot be written if the two collapse.
    SuiteWithdrawn,
    SuiteBelowPolicy,
    /// The key did not resolve.
    ///
    /// **Separate from [`Self::SignatureInvalid`], and the wire value is not.**
    /// §5.2.1 gives one class for the whole of authentication because
    /// distinguishing them tells a requester whether a key is *known*, which is
    /// relationship existence. An operator debugging still needs to know which,
    /// and the corpus asserts the internal reason — so this is the same shape as
    /// the two suite reasons: two causes, one value, and the collapse happens in
    /// the mapping rather than in the type.
    ///
    /// An earlier version of this enum had one variant here, on the reasoning
    /// that "two values would invite two responses". That reasoning applies to
    /// the *wire* value and was applied to the wrong half.
    KeyUnresolvable,
    /// The signature did not verify.
    SignatureInvalid,
    /// The verified payload does not parse, is not an object, or has no usable
    /// `signature` member.
    ///
    /// It does **not** yet cover every field §2 requires. §5.2.1's row says a
    /// core object missing one is `malformed`, and checking that is core-object
    /// validation rather than suite verification — P-005's, and the corpus's
    /// `core_object_missing_required_field` vector belongs to whoever builds
    /// it. Named here because the gap is easier to find at the variant than in
    /// a PRD.
    CoreObjectMalformed,
    /// The verified object carries `signature.value`.
    ///
    /// Under `eddsa-jws-2026` the value **is the third compact segment** and is
    /// therefore not a member of the object the suite serializes — an object
    /// containing the signature over itself is not constructible (E-31). A
    /// payload carrying one is a shape no conforming producer emits, and
    /// returning it would let everything downstream see a core object that
    /// cannot exist.
    ///
    /// `malformed` rather than `structurally_invalid`: the fault is in the
    /// **verified core object**, which is the half of §5.2.1's line that
    /// `malformed` covers.
    CoreObjectCarriesSignatureValue,
    /// The five parse failures `message/reject/` keeps apart.
    ///
    /// All `malformed` on the wire — §5.2.1 collapses them because each is
    /// visible in the message the requester produced — and each a different
    /// fact for an operator, which is why `parse` reports a cause rather than
    /// only a message.
    CoreObjectDuplicateKey,
    CoreObjectFloat,
    CoreObjectTooDeep,
    CoreObjectTooManyMembers,
    CoreObjectStringTooLong,
    /// `q2d_version` is a string this build does not implement.
    ///
    /// Step 5 and not earlier: the authoritative version is inside the signed
    /// object, so it cannot be read before verification. `routing` may carry a
    /// copy and §4 step 2 may shed on it, but that is load shedding and never a
    /// rejection reason.
    UnsupportedVersion,
    /// The header and the payload disagree.
    HeaderPayloadSuiteMismatch,
    HeaderPayloadKeyMismatch,
}

impl Rejected {
    /// The value a requester receives — `core-model.md` §5.2.1.
    ///
    /// A **separate function** rather than a field, so that the internal reason
    /// and the external one cannot be the same variable by accident. Several
    /// internal reasons map to one external value, which is the direction that
    /// is correct; no internal reason maps to two.
    pub fn external_reason(&self) -> &'static str {
        match self {
            Rejected::CompactSegmentCount
            | Rejected::HeaderSegmentNotBase64url
            | Rejected::PayloadSegmentNotBase64url
            | Rejected::SignatureSegmentNotBase64url
            | Rejected::HeaderNotAnObject
            | Rejected::HeaderMemberNotAString
            | Rejected::HeaderMemberNotPermitted
            | Rejected::HeaderPayloadSuiteMismatch
            | Rejected::HeaderPayloadKeyMismatch => "structurally_invalid",
            Rejected::SuiteUnregistered
            | Rejected::SuiteWithdrawn
            | Rejected::SuiteBelowPolicy => "unsupported_suite",
            Rejected::KeyUnresolvable | Rejected::SignatureInvalid => "unauthenticated",
            Rejected::CoreObjectMalformed
            | Rejected::CoreObjectCarriesSignatureValue
            | Rejected::CoreObjectDuplicateKey
            | Rejected::CoreObjectFloat
            | Rejected::CoreObjectTooDeep
            | Rejected::CoreObjectTooManyMembers
            | Rejected::CoreObjectStringTooLong => "malformed",
            Rejected::UnsupportedVersion => "unsupported_version",
        }
    }

    /// The `core-model.md` §4 step at which this is caught.
    ///
    /// A string, because §4's steps are not all numbers: the header/payload
    /// comparison is step **5a**, lettered so the steps below it did not
    /// renumber when E-35 added it.
    pub fn step(&self) -> &'static str {
        match self {
            Rejected::CompactSegmentCount
            | Rejected::HeaderSegmentNotBase64url
            | Rejected::PayloadSegmentNotBase64url
            | Rejected::SignatureSegmentNotBase64url
            | Rejected::HeaderNotAnObject
            | Rejected::HeaderMemberNotAString
            | Rejected::HeaderMemberNotPermitted
            | Rejected::SuiteUnregistered
            | Rejected::SuiteWithdrawn
            | Rejected::SuiteBelowPolicy => "3",
            Rejected::KeyUnresolvable | Rejected::SignatureInvalid => "4",
            Rejected::CoreObjectMalformed
            | Rejected::CoreObjectCarriesSignatureValue
            | Rejected::CoreObjectDuplicateKey
            | Rejected::CoreObjectFloat
            | Rejected::CoreObjectTooDeep
            | Rejected::CoreObjectTooManyMembers
            | Rejected::CoreObjectStringTooLong
            | Rejected::UnsupportedVersion => "5",
            // **Lettered.** §4's query order names step `5a` for the two
            // comparisons, which E-35 added. A numeric type could not carry it,
            // and the corpus asserts the step as the specification writes it.
            Rejected::HeaderPayloadSuiteMismatch | Rejected::HeaderPayloadKeyMismatch => "5a",
        }
    }
}

impl fmt::Display for Rejected {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        // Names the reason and never a value from the message.
        let text = match self {
            Rejected::CompactSegmentCount => "`signed` is not three segments",
            Rejected::HeaderSegmentNotBase64url => "the header segment is not base64url",
            Rejected::PayloadSegmentNotBase64url => "the payload segment is not base64url",
            Rejected::SignatureSegmentNotBase64url => "the signature segment is not base64url",
            Rejected::HeaderNotAnObject => "the protected header is not an object",
            Rejected::HeaderMemberNotAString => "a protected header member is not a string",
            Rejected::HeaderMemberNotPermitted => {
                "the protected header carries a member crypto-suites.md §3 does not permit"
            }
            Rejected::SuiteUnregistered => "the declared suite is not registered",
            Rejected::SuiteWithdrawn => "the declared suite is withdrawn",
            Rejected::SuiteBelowPolicy => "the declared suite is outside the acceptable set",
            Rejected::KeyUnresolvable => "the key did not resolve",
            Rejected::SignatureInvalid => "the signature did not verify",
            Rejected::CoreObjectMalformed => "the verified payload is not a core object",
            Rejected::CoreObjectDuplicateKey => "the verified object has a duplicate key",
            Rejected::CoreObjectFloat => "the verified object carries a floating-point value",
            Rejected::CoreObjectTooDeep => "the verified object nests past the limit",
            Rejected::CoreObjectTooManyMembers => "an object in the payload has too many members",
            Rejected::CoreObjectStringTooLong => "a string in the payload is past its limit",
            Rejected::CoreObjectCarriesSignatureValue => {
                "the verified object carries `signature.value`, which this suite puts in the third segment"
            }
            Rejected::UnsupportedVersion => "the verified object declares a version this build does not implement",
            Rejected::HeaderPayloadSuiteMismatch => "the header and payload declare different suites",
            Rejected::HeaderPayloadKeyMismatch => "the header and payload declare different keys",
        };
        write!(f, "{text}")
    }
}

impl From<SignatureInvalid> for Rejected {
    fn from(_: SignatureInvalid) -> Self {
        // Only ever from the signature check — key resolution maps its own
        // failure explicitly, because the two are different facts and this
        // conversion cannot tell them apart.
        Rejected::SignatureInvalid
    }
}

/// The protected header, after §3's member set has been checked.
struct Header {
    suite: String,
    key_id: String,
}

/// Read the header — step 1, and §3's closed member set.
///
/// This runs **before** anything is authenticated, which is why it reads as
/// little as possible: two members, both strings, nothing else permitted. Every
/// member here is a pre-authentication input surface.
fn read_header(segment: &str) -> Result<Header, Rejected> {
    let bytes = base64url::decode(segment).map_err(|_| Rejected::HeaderSegmentNotBase64url)?;
    // The crate's own parser: duplicate keys are refused rather than resolved,
    // so a header carrying `suite` twice is not a header with one of them.
    let value = crate::parse(&bytes).map_err(|_| Rejected::HeaderNotAnObject)?;
    let members = match value {
        Value::Object(members) => members,
        _ => return Err(Rejected::HeaderNotAnObject),
    };

    // Closed. An `alg` member is rejected here, by the set rather than by a
    // rule naming it — and so is any parameter that would weaken verification,
    // which is issue 12's vector. No special case exists for either, and none
    // may be added.
    for name in members.keys() {
        if name != "suite" && name != "key_id" {
            return Err(Rejected::HeaderMemberNotPermitted);
        }
    }
    let text = |name: &str| match members.get(name) {
        Some(Value::String(s)) => Ok(s.clone()),
        _ => Err(Rejected::HeaderMemberNotAString),
    };
    Ok(Header {
        suite: text("suite")?,
        key_id: text("key_id")?,
    })
}

/// Verify a query envelope's `signed` string, returning the verified core
/// object.
///
/// The four steps in order. Nothing below step 3 runs for a suite the policy
/// does not accept, and nothing below step 4 runs for an unauthenticated
/// message.
pub fn verify_query(
    signed: &str,
    policy: &SuitePolicy,
    registry: &SuiteRegistry,
    resolver: &dyn KeyResolver,
) -> Result<Value, Rejected> {
    // The container, before the header: a string that is not three segments has
    // no header to read.
    let mut parts = signed.split('.');
    let (header_segment, payload_segment, signature_segment) =
        match (parts.next(), parts.next(), parts.next(), parts.next()) {
            (Some(h), Some(p), Some(s), None) => (h, p, s),
            _ => return Err(Rejected::CompactSegmentCount),
        };

    // Step 1, and the container's other half: **all three segments must be
    // base64url, and that is checked here rather than left to verification.**
    // A signature segment that will not decode is a fault in the container
    // `crypto-suites.md` §3 defines, not an authentication failure — E-46, and
    // the corpus is where the two implementations agree on it.
    let header = read_header(header_segment)?;
    base64url::decode(payload_segment).map_err(|_| Rejected::PayloadSegmentNotBase64url)?;
    base64url::decode(signature_segment).map_err(|_| Rejected::SignatureSegmentNotBase64url)?;

    // Step 2 — the whole defence.
    //
    // Registry first, then policy, which is the order the two internal reasons
    // need: a suite that is not registered cannot also be below a floor. Both
    // reach one wire value — §5.2.1's `unsupported_suite` is one value for two
    // causes, so a requester cannot learn whether the custodian *knows* the
    // suite it declined.
    let entry = registry
        .resolve(&header.suite)
        .map_err(|_| Rejected::SuiteUnregistered)?;
    // Status before policy, which is the order they can be told apart in: a
    // suite the registry has withdrawn is refused whatever a deployment
    // configured, so reading policy first would report a local decision for a
    // refusal that was not local. All three reach §5.2.1's `unsupported_suite`.
    if !entry.status().may_verify() {
        return Err(Rejected::SuiteWithdrawn);
    }
    if !policy.accepts(&header.suite) {
        return Err(Rejected::SuiteBelowPolicy);
    }

    // Step 3 — verify with the entry's parameters. The header supplied an
    // identifier and nothing else; `entry` is what says how to verify, and this
    // build implements exactly one suite (`policy::IMPLEMENTED`), which step 2
    // has already established.
    let key = resolver
        .resolve(&header.key_id)
        .map_err(|_| Rejected::KeyUnresolvable)?;
    let payload = jws::verify_compact_parts(
        signed,
        header_segment,
        payload_segment,
        signature_segment,
        &key,
    )?;

    // Step 5 — parse the verified object. Not before: §2.1 is explicit.
    //
    // **The five `message/reject/` keeps apart.** All `malformed` on the wire
    // and each a different fact for an operator, which is why [`crate::parse`]
    // reports a [`ParseCause`](crate::parse::ParseCause) rather than only a
    // message. Recovering them by matching prose would be a second place that
    // decides what a parse failure was.
    let core = crate::parse(&payload).map_err(|error| match error.cause() {
        crate::parse::ParseCause::DuplicateKey => Rejected::CoreObjectDuplicateKey,
        crate::parse::ParseCause::Float => Rejected::CoreObjectFloat,
        crate::parse::ParseCause::TooDeep => Rejected::CoreObjectTooDeep,
        crate::parse::ParseCause::TooManyMembers => Rejected::CoreObjectTooManyMembers,
        crate::parse::ParseCause::StringTooLong => Rejected::CoreObjectStringTooLong,
        // An integer outside `i64` and everything RFC 8259 itself refuses are
        // one fact to an operator — *this is not a core object* — and no vector
        // distinguishes them.
        crate::parse::ParseCause::IntegerOutOfRange | crate::parse::ParseCause::Other => {
            Rejected::CoreObjectMalformed
        }
    })?;

    // Step 5a — the two comparisons. After parsing, because neither can be made
    // before it.
    let signature = match &core {
        Value::Object(members) => members.get("signature"),
        _ => return Err(Rejected::CoreObjectMalformed),
    };
    let declared = |name: &str| match signature {
        Some(Value::Object(members)) => match members.get(name) {
            Some(Value::String(s)) => Ok(s.as_str()),
            _ => Err(Rejected::CoreObjectMalformed),
        },
        _ => Err(Rejected::CoreObjectMalformed),
    };
    if declared("profile")? != header.suite {
        return Err(Rejected::HeaderPayloadSuiteMismatch);
    }
    if declared("key_id")? != header.key_id {
        return Err(Rejected::HeaderPayloadKeyMismatch);
    }


    // **After 5a, not before.** `crypto-suites.md` §3 puts the two comparisons
    // *"immediately after the payload is parsed… and before any step that acts
    // on a payload field"*, and `q2d_version` is a payload field. A message
    // that is both a version this build does not implement and a
    // header/payload disagreement answers with the disagreement.
    //
    // Beyond that ordering, the version is read before anything **else** in the
    // object: a 0.2 message may have moved or retyped any field, so
    // interpreting one to build a better diagnostic would be a guess presented
    // as fact.
    crate::check_version(&core).map_err(|problem| match problem {
        crate::VersionProblem::Unsupported => Rejected::UnsupportedVersion,
        crate::VersionProblem::Malformed => Rejected::CoreObjectMalformed,
    })?;

    // E-31, **last**: `signature.value` is one of the fields the version check
    // above means when it says *anything else in the object*. A payload that is
    // both an unimplemented version and carries a value answers with the
    // version, because under 0.2 the member might not mean what it means here.
    if matches!(&core, Value::Object(m) if matches!(m.get("signature"),
        Some(Value::Object(s)) if s.contains_key("value")))
    {
        return Err(Rejected::CoreObjectCarriesSignatureValue);
    }

    Ok(core)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::ed25519::PrivateKey;
    use crate::keys::FixedKeys;
    use crate::suites::SuiteRegistry;

    fn repo(parts: &[&str]) -> std::path::PathBuf {
        let mut path = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"));
        path.extend(parts);
        path
    }

    fn registry() -> SuiteRegistry {
        SuiteRegistry::load(&std::fs::read(repo(&["registry", "suites.json"])).unwrap()).unwrap()
    }

    fn seed(key_id: &str) -> Vec<u8> {
        let document =
            crate::parse(&std::fs::read(repo(&["conformance", "keys", "ed25519-test-only.json"]))
                .unwrap())
            .unwrap();
        let text = match &document {
            Value::Object(top) => match &top["keys"] {
                Value::Object(keys) => match &keys[key_id] {
                    Value::Object(entry) => match &entry["seed"] {
                        Value::String(s) => s.clone(),
                        _ => panic!("seed"),
                    },
                    _ => panic!("key"),
                },
                _ => panic!("keys"),
            },
            _ => panic!("document"),
        };
        (0..text.len())
            .step_by(2)
            .map(|i| u8::from_str_radix(&text[i..i + 2], 16).unwrap())
            .collect()
    }

    fn resolver() -> FixedKeys {
        let mut keys = FixedKeys::new();
        for id in ["test-requester-1", "test-requester-2", "test-custodian-1"] {
            let public = PrivateKey::from_seed(&seed(id)).unwrap().public_key();
            keys = keys.with(id, &public.to_bytes()).unwrap();
        }
        keys
    }

    fn policy() -> SuitePolicy {
        SuitePolicy::from_config(&registry(), &[]).unwrap()
    }

    /// The canonical query, signed — the same string the corpus asserts.
    fn signed() -> String {
        std::fs::read_to_string(repo(&["testdata", "canonical-query.signed"]))
            .unwrap()
            .trim_end()
            .to_string()
    }

    fn verify(signed: &str) -> Result<Value, Rejected> {
        verify_query(signed, &policy(), &registry(), &resolver())
    }

    #[test]
    fn a_valid_query_verifies_and_returns_the_core_object() {
        let core = verify(&signed()).expect("the canonical query verifies");
        match &core {
            Value::Object(members) => {
                assert!(members.contains_key("predicate"));
                // No `signature.value` reattached: under this suite it is the
                // third segment and not a member of the object (E-31).
                match &members["signature"] {
                    Value::Object(signature) => assert!(!signature.contains_key("value")),
                    _ => panic!("signature"),
                }
            }
            _ => panic!("not an object"),
        }
    }

    #[test]
    fn the_container_is_checked_before_the_header() {
        assert_eq!(verify("only.two").unwrap_err(), Rejected::CompactSegmentCount);
        assert_eq!(verify("").unwrap_err(), Rejected::CompactSegmentCount);
        let parts: Vec<&str> = signed().split('.').map(|_| "").collect::<Vec<_>>();
        let _ = parts;
        let signed = signed();
        let (_, rest) = signed.split_once('.').unwrap();
        assert_eq!(
            verify(&format!("not base64url!.{rest}")).unwrap_err(),
            Rejected::HeaderSegmentNotBase64url
        );
    }

    #[test]
    fn a_header_member_section_3_does_not_permit_is_refused_at_step_3() {
        // Issue 12's case, and `alg` is only the famous instance: the member set
        // is closed, so a header carrying *anything* extra is refused before the
        // suite is looked up. No rule about `alg` exists, and none may be added.
        let key = PrivateKey::from_seed(&seed("test-requester-1")).unwrap();
        for extra in [r#""alg":"none""#, r#""alg":"HS256""#, r#""crit":["b64"]"#, r#""b64":false"#] {
            let header = format!(
                r#"{{"key_id":"test-requester-1",{extra},"suite":"eddsa-jws-2026"}}"#
            );
            let payload = signed();
            let payload = payload.split('.').nth(1).unwrap();
            let signing_input =
                format!("{}.{payload}", crate::base64url::encode(header.as_bytes()));
            let signature = key.sign(signing_input.as_bytes());
            let compact =
                format!("{signing_input}.{}", crate::base64url::encode(&signature));

            let rejected = verify(&compact).unwrap_err();
            assert_eq!(rejected, Rejected::HeaderMemberNotPermitted, "{extra}");
            assert_eq!(rejected.step(), "3", "{extra}");
            // And it is refused *without* verifying, which is the point: the
            // signature over these bytes is perfectly good.
            assert!(crate::ed25519::verify(
                &key.public_key(),
                signing_input.as_bytes(),
                &signature
            )
            .is_ok());
        }
    }

    #[test]
    fn a_suite_outside_the_acceptable_set_is_refused_before_verification() {
        // Step 2. Built by signing a header naming an unregistered suite — the
        // signature is valid, and the message is refused anyway.
        let key = PrivateKey::from_seed(&seed("test-requester-1")).unwrap();
        let payload = signed();
        let payload = payload.split('.').nth(1).unwrap();
        let header = br#"{"key_id":"test-requester-1","suite":"hmac-sha1-1999"}"#;
        let signing_input = format!("{}.{payload}", crate::base64url::encode(header));
        let signature = key.sign(signing_input.as_bytes());
        let compact = format!("{signing_input}.{}", crate::base64url::encode(&signature));

        let rejected = verify(&compact).unwrap_err();
        assert_eq!(rejected, Rejected::SuiteUnregistered);
        assert_eq!(rejected.external_reason(), "unsupported_suite");
        assert_eq!(rejected.step(), "3");
    }

    #[test]
    fn an_unresolvable_key_is_indistinguishable_on_the_wire_from_a_bad_signature() {
        // §4.6's second invariant, at the sequence level. The two reach
        // *different* internal reasons — an operator needs to know which — and
        // the same wire value, which is where the requester's view collapses.
        let key = PrivateKey::from_seed(&seed("test-requester-1")).unwrap();
        let payload = signed();
        let payload = payload.split('.').nth(1).unwrap();
        let header = br#"{"key_id":"nobody-we-know","suite":"eddsa-jws-2026"}"#;
        let signing_input = format!("{}.{payload}", crate::base64url::encode(header));
        let signature = key.sign(signing_input.as_bytes());
        let unresolvable =
            format!("{signing_input}.{}", crate::base64url::encode(&signature));

        let mut tampered = signed();
        tampered.pop();
        tampered.push(if signed().ends_with('A') { 'B' } else { 'A' });

        // Different internal reasons, and the **same wire value** — which is
        // the separation §5.2 requires, in the direction that matters.
        let a = verify(&unresolvable).unwrap_err();
        let b = verify(&tampered).unwrap_err();
        assert_eq!(a, Rejected::KeyUnresolvable);
        assert_eq!(b, Rejected::SignatureInvalid);
        assert_ne!(a, b);
        assert_eq!(a.external_reason(), b.external_reason());
        assert_eq!(a.step(), b.step());
    }

    #[test]
    fn a_header_that_disagrees_with_the_payload_is_refused_after_verification() {
        // Issue 7. The header names a key the payload does not, and the
        // signature is made with *that* key — so verification succeeds and
        // nothing else would catch it.
        let key = PrivateKey::from_seed(&seed("test-requester-2")).unwrap();
        let payload = signed();
        let payload = payload.split('.').nth(1).unwrap();
        let header = br#"{"key_id":"test-requester-2","suite":"eddsa-jws-2026"}"#;
        let signing_input = format!("{}.{payload}", crate::base64url::encode(header));
        let signature = key.sign(signing_input.as_bytes());
        let compact = format!("{signing_input}.{}", crate::base64url::encode(&signature));

        let rejected = verify(&compact).unwrap_err();
        assert_eq!(rejected, Rejected::HeaderPayloadKeyMismatch);
        assert_eq!(rejected.external_reason(), "structurally_invalid");
    }

    #[test]
    fn a_version_this_build_does_not_implement_is_refused_at_step_5() {
        // `message/reject/unknown-version` in miniature. The version is inside
        // the signed object, so this is reachable only after verification —
        // which is why it is step 5 and why `routing`'s copy is load shedding
        // rather than a rejection reason.
        let key = PrivateKey::from_seed(&seed("test-requester-1")).unwrap();
        let query = crate::parse(&std::fs::read(repo(&["testdata", "canonical-query.json"])).unwrap())
            .unwrap();
        let mut members = match query {
            Value::Object(m) => m,
            _ => panic!("query"),
        };
        members.insert("q2d_version".into(), Value::String("0.2".into()));
        let payload = crate::serialize(&Value::Object(members)).unwrap();

        let header = br#"{"key_id":"test-requester-1","suite":"eddsa-jws-2026"}"#;
        let signing_input = format!(
            "{}.{}",
            crate::base64url::encode(header),
            crate::base64url::encode(&payload)
        );
        let signature = key.sign(signing_input.as_bytes());
        let compact = format!("{signing_input}.{}", crate::base64url::encode(&signature));

        let rejected = verify(&compact).unwrap_err();
        assert_eq!(rejected, Rejected::UnsupportedVersion);
        assert_eq!(rejected.external_reason(), "unsupported_version");
        assert_eq!(rejected.step(), "5");
    }

    impl Rejected {
        /// Every variant, derived rather than transcribed.
        ///
        /// `MAPPING` below is hand-written, and a hand-written list of every
        /// variant stops covering the type the moment someone adds one —
        /// silently, because nothing makes a `const` slice complete. So this
        /// list is built from a **total function**: `next` matches
        /// exhaustively, and a new variant does not compile until it has been
        /// placed in the order.
        ///
        /// That this was needed is not hypothetical. `MAPPING` carried
        /// `CoreObjectCarriesSignatureValue` twice, and no check noticed,
        /// because nothing compared the table against the type.
        fn every_variant() -> Vec<Rejected> {
            const fn next(reason: &Rejected) -> Option<Rejected> {
                match reason {
                    Rejected::CompactSegmentCount => Some(Rejected::HeaderSegmentNotBase64url),
                    Rejected::HeaderSegmentNotBase64url => Some(Rejected::PayloadSegmentNotBase64url),
                    Rejected::PayloadSegmentNotBase64url => Some(Rejected::SignatureSegmentNotBase64url),
                    Rejected::SignatureSegmentNotBase64url => Some(Rejected::HeaderNotAnObject),
                    Rejected::HeaderNotAnObject => Some(Rejected::HeaderMemberNotAString),
                    Rejected::HeaderMemberNotAString => Some(Rejected::HeaderMemberNotPermitted),
                    Rejected::HeaderMemberNotPermitted => Some(Rejected::SuiteUnregistered),
                    Rejected::SuiteUnregistered => Some(Rejected::SuiteWithdrawn),
                    Rejected::SuiteWithdrawn => Some(Rejected::SuiteBelowPolicy),
                    Rejected::SuiteBelowPolicy => Some(Rejected::KeyUnresolvable),
                    Rejected::KeyUnresolvable => Some(Rejected::SignatureInvalid),
                    Rejected::SignatureInvalid => Some(Rejected::CoreObjectMalformed),
                    Rejected::CoreObjectMalformed => Some(Rejected::CoreObjectCarriesSignatureValue),
                    Rejected::CoreObjectCarriesSignatureValue => Some(Rejected::CoreObjectDuplicateKey),
                    Rejected::CoreObjectDuplicateKey => Some(Rejected::CoreObjectFloat),
                    Rejected::CoreObjectFloat => Some(Rejected::CoreObjectTooDeep),
                    Rejected::CoreObjectTooDeep => Some(Rejected::CoreObjectTooManyMembers),
                    Rejected::CoreObjectTooManyMembers => Some(Rejected::CoreObjectStringTooLong),
                    Rejected::CoreObjectStringTooLong => Some(Rejected::UnsupportedVersion),
                    Rejected::UnsupportedVersion => Some(Rejected::HeaderPayloadSuiteMismatch),
                    Rejected::HeaderPayloadSuiteMismatch => Some(Rejected::HeaderPayloadKeyMismatch),
                    Rejected::HeaderPayloadKeyMismatch => None,
                }
            }
            let mut all = vec![Rejected::CompactSegmentCount];
            while let Some(following) = next(all.last().unwrap()) {
                all.push(following);
            }
            all
        }
    }

    #[test]
    fn the_mapping_to_a_wire_value_is_many_to_one_and_not_the_name() {
        // §5.2's separation. The check is not that the two *spell* differently
        // — `SignatureInvalid` and `signature_invalid` coincide, and §5.2.1 names
        // that class after its value on purpose. It is that the wire value is a
        // **mapping** rather than the variant's name in lower case: most of
        // these variants do not name their own wire value, and this table is
        // what both implementations must agree on.
        const MAPPING: &[(Rejected, &str, &str)] = &[
            (Rejected::CompactSegmentCount, "structurally_invalid", "3"),
            (Rejected::HeaderSegmentNotBase64url, "structurally_invalid", "3"),
            (Rejected::PayloadSegmentNotBase64url, "structurally_invalid", "3"),
            (Rejected::SignatureSegmentNotBase64url, "structurally_invalid", "3"),
            (Rejected::HeaderNotAnObject, "structurally_invalid", "3"),
            (Rejected::HeaderMemberNotAString, "structurally_invalid", "3"),
            (Rejected::HeaderMemberNotPermitted, "structurally_invalid", "3"),
            (Rejected::SuiteUnregistered, "unsupported_suite", "3"),
            (Rejected::SuiteWithdrawn, "unsupported_suite", "3"),
            (Rejected::SuiteBelowPolicy, "unsupported_suite", "3"),
            (Rejected::KeyUnresolvable, "unauthenticated", "4"),
            (Rejected::SignatureInvalid, "unauthenticated", "4"),
            (Rejected::CoreObjectMalformed, "malformed", "5"),
            (Rejected::CoreObjectDuplicateKey, "malformed", "5"),
            (Rejected::CoreObjectFloat, "malformed", "5"),
            (Rejected::CoreObjectTooDeep, "malformed", "5"),
            (Rejected::CoreObjectTooManyMembers, "malformed", "5"),
            (Rejected::CoreObjectStringTooLong, "malformed", "5"),
            (Rejected::CoreObjectCarriesSignatureValue, "malformed", "5"),
            (Rejected::UnsupportedVersion, "unsupported_version", "5"),
            (Rejected::HeaderPayloadSuiteMismatch, "structurally_invalid", "5a"),
            (Rejected::HeaderPayloadKeyMismatch, "structurally_invalid", "5a"),
        ];

        // The table covers the type. Without this it covers whatever it
        // covered on the day it was written.
        let mut tabled: Vec<Rejected> = MAPPING.iter().map(|(r, _, _)| r.clone()).collect();
        let mut all = Rejected::every_variant();
        assert_eq!(
            tabled.len(),
            all.len(),
            "a variant is missing from MAPPING, or is listed twice"
        );
        tabled.sort_by_key(|r| format!("{r:?}"));
        all.sort_by_key(|r| format!("{r:?}"));
        assert_eq!(tabled, all);

        let mut values = std::collections::BTreeSet::new();
        for (rejected, external, step) in MAPPING {
            assert_eq!(rejected.external_reason(), *external, "{rejected:?}");
            assert_eq!(rejected.step(), *step, "{rejected:?}");
            values.insert(*external);

            // No rejection's message carries anything from the message it is
            // about. §5.2's other half.
            let message = rejected.to_string();
            assert!(!message.contains("test-requester"), "{message}");
            assert!(!message.contains("eddsa"), "{message}");
        }

        // Many-to-one, which is the direction that is correct: several internal
        // reasons share a value so a requester cannot tell them apart, and no
        // internal reason has two.
        assert!(
            values.len() < MAPPING.len(),
            "every internal reason has its own wire value, which is the leak"
        );
        assert_eq!(values.len(), 5);
    }
}
