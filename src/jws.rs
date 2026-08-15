//! JWS compact construction — P-003 issue 5.
//!
//! ```text
//! signed        = BASE64URL(header) "." BASE64URL(payload) "." BASE64URL(signature)
//! signing_input = ASCII(BASE64URL(header) "." BASE64URL(payload))
//! ```
//!
//! `crypto-suites.md` §3 defines the container and the protected header's two
//! members. The payload is the byte string [`crate::serialize`] produced; this
//! module never builds one and never inspects one.
//!
//! ## Deterministic, which is what the corpus rests on
//!
//! Ed25519 is deterministic and [`crate::serialize`] is a fixed profile, so the
//! same key and the same logical query produce the same compact string every
//! time and in both languages. That is why `suite/sign/` can assert **bytes**
//! rather than merely check that the result verifies — and a both-verify
//! acceptance would pass two implementations that disagree about what they
//! emit, which is exactly the divergence Stage 1's gate exists to find.
//!
//! ## The header is serialized, not formatted
//!
//! Its two members go through [`crate::serialize`] like anything else, so
//! `key_id` precedes `suite` by the ordering `serialization.md` §1 fixes.
//! Writing the JSON by hand here would put a second serializer in the codebase
//! whose output has to match the first one's — which is the arrangement two
//! implementations drift in.

use crate::base64url;
use crate::ed25519::{PrivateKey, PublicKey, SignatureInvalid};
use crate::suites::SuiteEntry;
use crate::value::{serialize, ProfileError, Value};
use std::collections::BTreeMap;
use std::fmt;

/// Why a compact JWS could not be produced.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SignError(String);

impl fmt::Display for SignError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.0)
    }
}

impl std::error::Error for SignError {}

impl From<ProfileError> for SignError {
    fn from(error: ProfileError) -> Self {
        SignError(format!("the protected header does not serialize: {error}"))
    }
}

/// Build the protected header `crypto-suites.md` §3 defines.
///
/// **Exactly two members, and no others.** The set is closed because the header
/// is read before verification, so every member is a pre-authentication input
/// surface — and because a header a general-purpose JOSE library can process is
/// one where that library selects the verification algorithm from
/// attacker-controlled data.
fn protected_header(suite: &str, key_id: &str) -> Value {
    let mut members = BTreeMap::new();
    members.insert("key_id".to_string(), Value::String(key_id.to_string()));
    members.insert("suite".to_string(), Value::String(suite.to_string()));
    Value::Object(members)
}

/// Sign `payload`, producing the compact serialization.
///
/// `payload` is bytes and stays bytes: this module signs what it is handed. The
/// caller produced it with [`crate::serialize`], and re-serializing here would
/// mean two paths to the signed bytes with nothing holding them together.
///
/// **Takes the registry entry, not a suite identifier.** `crypto-suites.md` §6
/// refuses production under a `deprecated` or `withdrawn` suite, and a
/// signature taking a bare string would let a caller sign under one by naming
/// it — the check would exist somewhere else and be forgotten here. Resolving
/// the suite is how you get an entry, so the status is in hand by construction.
pub fn sign(
    payload: &[u8],
    key: &PrivateKey,
    suite: &SuiteEntry,
    key_id: &str,
) -> Result<String, SignError> {
    if !suite.status.may_produce() {
        // The asymmetry in §6: this same suite may still *verify*. Refusing
        // here and not there is the whole point, because receipts signed under
        // it remain evidence.
        return Err(SignError(format!(
            "`{}` may not be produced under: `crypto-suites.md` §6 permits              production under an active suite only",
            suite.id
        )));
    }
    let header = serialize(&protected_header(&suite.id, key_id))?;
    let signing_input = format!(
        "{}.{}",
        base64url::encode(&header),
        base64url::encode(payload)
    );
    // ASCII by construction: base64url's alphabet and a dot.
    let signature = key.sign(signing_input.as_bytes());
    Ok(format!(
        "{signing_input}.{}",
        base64url::encode(&signature)
    ))
}

/// Split a compact serialization into its three segments.
///
/// Structural only — nothing here verifies anything, and a caller that used the
/// payload without verifying first would be violating `core-model.md` §4's
/// ordering. [`crate::jws::verify_compact`] is how a payload is obtained.
fn segments(compact: &str) -> Result<(&str, &str, &str), SignatureInvalid> {
    let mut parts = compact.split('.');
    match (parts.next(), parts.next(), parts.next(), parts.next()) {
        (Some(header), Some(payload), Some(signature), None) => Ok((header, payload, signature)),
        // Two segments, four segments, none: all the same answer. A compact
        // serialization has three, and the count is not negotiable.
        _ => Err(SignatureInvalid),
    }
}

/// Verify a compact serialization and return the **payload bytes**.
///
/// Bytes rather than a parsed object, deliberately — P-003 §9 item 7.
/// `core-model.md` §4 steps 4–5 require verification before parsing, and
/// returning bytes makes that a type-level fact. There is no way to obtain a parsed core object from
/// this module without having verified it first.
///
/// This is **not** §4.2's four-step sequence — it does not read the suite, does
/// not consult a policy, and does not compare the header against the payload.
/// Those need P-003 issue 6, which waits on
/// [E-46](https://github.com/q2d-protocol/q2d/blob/main/docs/open-escalations.md).
/// What this does is the cryptographic half, so that issue 6 is the ordering
/// and the policy rather than the ordering, the policy and the mathematics.
pub fn verify_compact(compact: &str, key: &PublicKey) -> Result<Vec<u8>, SignatureInvalid> {
    let (header, payload, signature) = segments(compact)?;
    // **All three segments must be base64url**, including the one this function
    // does not read. `crypto-suites.md` §3 defines the form as
    // `BASE64URL(header) "." BASE64URL(payload) "." BASE64URL(signature)`, and
    // a producer chooses its own header text — so without this, a signature
    // over a malformed header verifies and this returns a payload from a
    // message that is not a Q2D signed string. The caller would fail later
    // trying to read the suite out of it, which is a different function's job
    // and not a reason to hand it bytes.
    base64url::decode(header).map_err(|_| SignatureInvalid)?;
    let signature = base64url::decode(signature).map_err(|_| SignatureInvalid)?;
    // The signing input is the received text of the first two segments, not a
    // re-encoding of what they decode to. Re-encoding would make verification
    // depend on this implementation's encoder agreeing with the sender's, which
    // is the canonicalization dependency signing received bytes exists to
    // remove.
    let signing_input = &compact[..header.len() + 1 + payload.len()];
    crate::ed25519::verify(key, signing_input.as_bytes(), &signature)?;
    base64url::decode(payload).map_err(|_| SignatureInvalid)
}

#[cfg(test)]
mod tests {
    use super::*;

    /// The registered entry, from the reference registry, so the tests sign
    /// through the same path production does.
    fn suite() -> crate::suites::SuiteEntry {
        let path = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
            .join("registry")
            .join("suites.json");
        crate::suites::SuiteRegistry::load(&std::fs::read(path).expect("registry"))
            .expect("loads")
            .resolve("eddsa-jws-2026")
            .expect("registered")
            .clone()
    }

    fn key() -> PrivateKey {
        let path = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
            .join("conformance")
            .join("keys")
            .join("ed25519-test-only.json");
        let document = crate::parse(&std::fs::read(path).expect("key material")).unwrap();
        let seed = match &document {
            Value::Object(top) => match &top["keys"] {
                Value::Object(keys) => match &keys["test-requester-1"] {
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
        let bytes: Vec<u8> = (0..seed.len())
            .step_by(2)
            .map(|i| u8::from_str_radix(&seed[i..i + 2], 16).unwrap())
            .collect();
        PrivateKey::from_seed(&bytes).unwrap()
    }

    #[test]
    fn the_header_carries_two_members_in_the_profile_order() {
        let header = serialize(&protected_header("eddsa-jws-2026", "test-requester-1")).unwrap();
        // `key_id` before `suite`, which is `serialization.md` §1's ordering and
        // not the order they are written above.
        assert_eq!(
            header,
            br#"{"key_id":"test-requester-1","suite":"eddsa-jws-2026"}"#
        );
    }

    #[test]
    fn signing_is_deterministic_and_round_trips() {
        let key = key();
        let payload = br#"{"a":1}"#;
        let first = sign(payload, &key, &suite(), "test-requester-1").unwrap();
        assert_eq!(first, sign(payload, &key, &suite(), "test-requester-1").unwrap());
        assert_eq!(
            verify_compact(&first, &key.public_key()).unwrap(),
            payload.to_vec()
        );
    }

    #[test]
    fn the_compact_form_is_three_base64url_segments() {
        let compact = sign(b"{}", &key(), &suite(), "test-requester-1").unwrap();
        let parts: Vec<&str> = compact.split('.').collect();
        assert_eq!(parts.len(), 3);
        for part in parts {
            assert!(base64url::decode(part).is_ok(), "{part} is not base64url");
        }
    }

    #[test]
    fn a_wrong_segment_count_is_refused() {
        let key = key();
        let compact = sign(b"{}", &key, &suite(), "test-requester-1").unwrap();
        let public = key.public_key();
        for broken in [
            compact.replace('.', ""),                       // one segment
            compact.splitn(3, '.').take(2).collect::<Vec<_>>().join("."), // two
            format!("{compact}.extra"),                     // four
            String::new(),
        ] {
            assert!(verify_compact(&broken, &public).is_err(), "{broken}");
        }
    }

    #[test]
    fn a_suite_that_may_not_produce_refuses_to_sign() {
        // §6's asymmetry, at the producing end. The same entry may still be
        // acceptable to a verifier — `policy` decides that — and this refuses
        // regardless, because production is where a deprecated suite stops.
        let mut entry = suite();
        for status in [crate::SuiteStatus::Deprecated, crate::SuiteStatus::Withdrawn] {
            entry.status = status;
            let error = sign(b"{}", &key(), &entry, "test-requester-1").unwrap_err();
            assert!(error.to_string().contains("eddsa-jws-2026"), "{error}");
        }
    }

    #[test]
    fn a_segment_that_is_not_base64url_is_refused_even_when_signed() {
        // The signature is over the *text* of the first two segments, so a
        // producer can sign a header that is not base64url and the signature
        // verifies. §3 says what the form is, and this is where the form is
        // checked — otherwise a caller receives a payload from a message that
        // is not a Q2D signed string.
        let key = key();
        let payload_text = base64url::encode(b"{}");
        for header_text in ["not base64url!", "AAAA=", "Zh"] {
            let signing_input = format!("{header_text}.{payload_text}");
            let signature = key.sign(signing_input.as_bytes());
            let compact = format!("{signing_input}.{}", base64url::encode(&signature));
            // The signature is genuinely valid over these bytes...
            assert!(
                crate::ed25519::verify(&key.public_key(), signing_input.as_bytes(), &signature)
                    .is_ok()
            );
            // ...and the message is still refused.
            assert!(
                verify_compact(&compact, &key.public_key()).is_err(),
                "{header_text}"
            );
        }
    }

    #[test]
    fn a_tampered_payload_is_refused() {
        let key = key();
        let compact = sign(br#"{"a":1}"#, &key, &suite(), "test-requester-1").unwrap();
        let (header, _, signature) = segments(&compact).unwrap();
        let swapped = format!("{header}.{}.{signature}", base64url::encode(br#"{"a":2}"#));
        assert!(verify_compact(&swapped, &key.public_key()).is_err());
    }

    #[test]
    fn a_tampered_header_is_refused() {
        // The header is covered by the signature, which is the reason it can
        // carry the suite at all.
        let key = key();
        let compact = sign(b"{}", &key, &suite(), "test-requester-1").unwrap();
        let (_, payload, signature) = segments(&compact).unwrap();
        let other = serialize(&protected_header("eddsa-jws-2026", "test-requester-2")).unwrap();
        let swapped = format!("{}.{payload}.{signature}", base64url::encode(&other));
        assert!(verify_compact(&swapped, &key.public_key()).is_err());
    }

    #[test]
    fn verification_uses_the_received_text_not_a_re_encoding() {
        // A payload segment spelled with a non-canonical trailing bit decodes to
        // the same bytes. If verification re-encoded the decoded payload to
        // build the signing input, this would verify — and the module would have
        // reintroduced the canonicalization dependency.
        //
        // `base64url::decode` refuses the respelling outright, so the failure is
        // guaranteed; the value of the test is that it pins *why* the signing
        // input is a slice of the input rather than something rebuilt.
        let key = key();
        let compact = sign(b"{}", &key, &suite(), "test-requester-1").unwrap();
        let (header, payload, signature) = segments(&compact).unwrap();
        let alphabet = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_";
        let last = alphabet
            .iter()
            .position(|c| *c == payload.as_bytes()[payload.len() - 1])
            .unwrap();
        if last & 1 == 0 {
            let respelt = format!(
                "{}{}",
                &payload[..payload.len() - 1],
                alphabet[last | 1] as char
            );
            let broken = format!("{header}.{respelt}.{signature}");
            assert!(verify_compact(&broken, &key.public_key()).is_err());
        }
    }
}
