//! Ed25519 signing and verification, with the acceptance criteria pinned.
//!
//! P-003 issue 1. The curve arithmetic is [`ed25519_dalek`]'s, not this
//! crate's — `CONVENTIONS-rust.md` records why, and it is the one place in
//! either implementation where a dependency is not a convenience.
//!
//! ## Which signatures verify
//!
//! **`crypto-suites.md` §3 states the rule; this module implements it.** It is
//! there rather than here because "Ed25519" does not name one verification
//! rule — RFC 8032 leaves choices open and libraries take them differently, so
//! a third implementation building from `spec/` alone would otherwise pick its
//! own edge cases and disagree with both of these about whether a message is
//! authentic.
//!
//! Repeated here because this is where the code is, and a reader checking the
//! code against the rule should not have to hold it in their head. The
//! specification governs; if these ever disagree, this comment is the bug:
//!
//! 1. The public key is 32 bytes and decodes to a point on the curve, with a
//!    **canonical** field encoding.
//! 2. The signature is 64 bytes. `R` decodes to a point; `S` is **canonical**,
//!    meaning `S < L`.
//! 3. Neither `A` nor `R` has small order — that is, `[8]A` and `[8]R` are not
//!    the identity.
//! 4. The cofactorless verification equation holds:
//!    `[S]B = R + [SHA-512(R ‖ A ‖ M) mod L]A`.
//!
//! Rules 1, 2 and 3 are the ones that are optional elsewhere, and each decides
//! a real case:
//!
//! - **A non-canonical field encoding.** `y` may be written as `y + p` for
//!   nineteen values, twelve of which are points on the curve. Both libraries
//!   accept them — this is not a difference between the two implementations but
//!   a rule neither was applying, and it is applied here, in bytes, so that
//!   both run the identical test.
//! - **Non-canonical `S`.** `S` and `S + L` are two encodings of one scalar.
//!   Without the check, every signature has a second form that verifies, and a
//!   `signed` string can be altered in transit while still verifying — a
//!   different `request_digest` for one exchange (`core-model.md` §6).
//! - **Small-order `A`.** With `A = R = the identity point` and `S = 0`, the
//!   equation reduces to `identity = identity` and holds **for every
//!   message**. That is a universal forgery requiring no private key, and it
//!   is accepted by Go's `crypto/ed25519.Verify`, which is why `ed25519.go`
//!   carries an explicit small-order check rather than calling the standard
//!   library alone.
//!
//! `testdata/ed25519-acceptance.txt` is that table as a fixture, and both
//! implementations are held to it.
//!
//! ## Not constant-time, and not claimed to be
//!
//! Verification handles no secret. Signing does, and `ed25519_dalek` documents
//! its own timing properties; this module adds no branch on key material. What
//! Q2D does **not** claim is resistance to physical side channels —
//! `claims.md` has no such claim and this module does not create one.

use ed25519_dalek::{Signature, Signer, SigningKey, VerifyingKey};

/// Is a compressed point's field element canonically encoded?
///
/// A compressed Edwards point is the y-coordinate in the low 255 bits and the
/// sign of x in the top one. Canonical means `y < p`, and `p = 2^255 - 19`
/// leaves exactly nineteen values above it — twelve of which decode to a point
/// on the curve, so this is not a theoretical set.
///
/// **Neither library enforces this.** `ed25519-dalek` accepts a non-canonical
/// `A`, and so does `filippo.io/edwards25519`, and they accept the same ones —
/// so this is not a divergence between the two implementations but a rule
/// stated in both module headers that neither was applying. Written as a byte
/// comparison rather than reached for through a curve library, so that Rust and
/// Go run the identical test rather than two libraries' opinions of it.
///
/// It matters because a key is pinned as bytes. Two spellings of one point are
/// two `key_id` bindings for one signer, and any comparison made on bytes
/// rather than on points sees two different keys.
fn canonical_point(encoded: &[u8; 32]) -> bool {
    // p = 2^255 - 19, little-endian, with the sign bit masked off.
    let mut y = *encoded;
    y[31] &= 0x7f;
    // Compare against p from the top down.
    const P: [u8; 32] = [
        0xed, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
        0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
        0xff, 0x7f,
    ];
    for i in (0..32).rev() {
        if y[i] != P[i] {
            return y[i] < P[i];
        }
    }
    false // y == p is not below it
}

/// Why a signature is not acceptable.
///
/// One value. The causes are deliberately not distinguished: `core-model.md`
/// §5.2.1 gives one external class for the whole of authentication, and an
/// internal type with four variants invites a caller to map them onto four
/// responses.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SignatureInvalid;

impl std::fmt::Display for SignatureInvalid {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        // No detail, and none is coming: which of the four rules failed is a
        // fact about attacker-supplied bytes.
        write!(f, "signature does not verify")
    }
}

impl std::error::Error for SignatureInvalid {}

/// A public key that has been checked far enough to be worth keeping.
///
/// Constructing one runs rules 1 and the `A` half of rule 3, so a small-order
/// key cannot reach [`verify`] at all — the check is in the type rather than
/// in each call site.
#[derive(Debug, Clone)]
pub struct PublicKey(VerifyingKey);

/// A private key. Test material only in this repository — see
/// `conformance/keys/README.md`.
pub struct PrivateKey(SigningKey);

impl PublicKey {
    /// Decode a 32-byte public key, refusing anything rules 1 and 3 exclude.
    pub fn from_bytes(bytes: &[u8]) -> Result<Self, SignatureInvalid> {
        let array: [u8; 32] = bytes.try_into().map_err(|_| SignatureInvalid)?;
        if !canonical_point(&array) {
            return Err(SignatureInvalid);
        }
        let key = VerifyingKey::from_bytes(&array).map_err(|_| SignatureInvalid)?;
        // `is_weak` is dalek's name for small order. Checked here as well as by
        // `verify_strict` below, so that a caller holding a `PublicKey` knows
        // it is not one — key resolution rejects rather than every verify.
        if key.is_weak() {
            return Err(SignatureInvalid);
        }
        Ok(PublicKey(key))
    }

    /// The 32-byte encoding.
    pub fn to_bytes(&self) -> [u8; 32] {
        self.0.to_bytes()
    }
}

impl PrivateKey {
    /// A key from its 32-byte seed, as RFC 8032 §5.1.5 defines one.
    pub fn from_seed(seed: &[u8]) -> Result<Self, SignatureInvalid> {
        let array: [u8; 32] = seed.try_into().map_err(|_| SignatureInvalid)?;
        Ok(PrivateKey(SigningKey::from_bytes(&array)))
    }

    /// The public key this seed derives.
    pub fn public_key(&self) -> PublicKey {
        PublicKey(self.0.verifying_key())
    }

    /// Sign `message`. Ed25519 is deterministic, so the same key and message
    /// always produce the same 64 bytes — which is what lets the corpus assert
    /// a signature rather than merely check one.
    pub fn sign(&self, message: &[u8]) -> [u8; 64] {
        self.0.sign(message).to_bytes()
    }
}

/// Verify `signature` over `message` under `key`, against the four rules above.
pub fn verify(key: &PublicKey, message: &[u8], signature: &[u8]) -> Result<(), SignatureInvalid> {
    let array: [u8; 64] = signature.try_into().map_err(|_| SignatureInvalid)?;
    // `R` is canonical for the same reason `A` is, and neither library checks
    // it. Unlike `A`, a non-canonical `R` does not survive verification anyway
    // — `R` is hashed as the bytes it arrived as, so a different spelling is a
    // different challenge — but the rule is stated, so it is applied where it
    // is stated rather than left to hold by accident somewhere else.
    let r: [u8; 32] = array[..32].try_into().expect("32 of 64");
    if !canonical_point(&r) {
        return Err(SignatureInvalid);
    }
    // `Signature::from_bytes` is infallible in dalek 3; `verify_strict` is what
    // enforces canonical `S` and rejects a small-order `R`. Calling `verify`
    // here instead would accept the identity forgery.
    let signature = Signature::from_bytes(&array);
    key.0
        .verify_strict(message, &signature)
        .map_err(|_| SignatureInvalid)
}

/// Verify without the strictness, **for tests only**.
///
/// Exists so `acceptance_differs_from_the_permissive_rule` can show that the
/// difference is real rather than asserted. Not exported outside the crate:
/// nothing in Q2D may call it.
#[cfg(test)]
fn verify_permissive(key: &PublicKey, message: &[u8], signature: &[u8]) -> bool {
    // `Verifier` is imported here rather than at the top of the module: it is
    // the trait carrying the permissive `verify`, and nothing outside this
    // function may reach it.
    use ed25519_dalek::Verifier;

    let Ok(array) = <[u8; 64]>::try_from(signature) else {
        return false;
    };
    key.0.verify(message, &Signature::from_bytes(&array)).is_ok()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn hex(s: &str) -> Vec<u8> {
        (0..s.len())
            .step_by(2)
            .map(|i| u8::from_str_radix(&s[i..i + 2], 16).unwrap())
            .collect()
    }

    /// RFC 8032 §7.1, read from the committed key material rather than
    /// repeated here.
    ///
    /// `conformance/keys/` is the one place a private seed lives — a test
    /// asserts that over every byte of every file in the repository, and it
    /// caught the first version of this module doing the obvious thing. The
    /// rule earns its keep twice over here: the gate now asserts that the
    /// material the **corpus** signs with reproduces RFC 8032, which is
    /// stronger than asserting it about a copy that could drift.
    ///
    /// Read with this crate's own parser rather than a JSON dependency or a
    /// hand-rolled scan. The first attempt was the scan, and it was wrong.
    fn known_answers() -> Vec<(Vec<u8>, Vec<u8>, Vec<u8>)> {
        use crate::value::Value;

        let path = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
            .join("conformance")
            .join("keys")
            .join("ed25519-test-only.json");
        let document = crate::parse(&std::fs::read(&path).expect("key material"))
            .expect("the key material parses");

        let object = |v: &Value, name: &str| -> Value {
            match v {
                Value::Object(members) => members.get(name).expect(name).clone(),
                _ => panic!("{name} is not in an object"),
            }
        };
        let string = |v: Value| -> String {
            match v {
                Value::String(s) => s,
                other => panic!("expected a string, found {other:?}"),
            }
        };

        let keys = object(&document, "keys");
        let answers: Vec<_> = match object(&document, "known_answers") {
            Value::Array(items) => items,
            _ => panic!("known_answers is not an array"),
        }
        .into_iter()
        .map(|answer| {
            let key_id = string(object(&answer, "key"));
            let seed = string(object(&object(&keys, &key_id), "seed"));
            (
                hex(&seed),
                hex(&string(object(&answer, "message"))),
                hex(&string(object(&answer, "signature"))),
            )
        })
        .collect();

        assert_eq!(answers.len(), 3, "the key material lost a known answer");
        answers
    }

    #[test]
    fn rfc_8032_known_answers() {
        for (seed, message, signature) in known_answers() {
            let key = PrivateKey::from_seed(&seed).unwrap();
            assert_eq!(key.sign(&message).to_vec(), signature, "a known answer");
            assert!(verify(&key.public_key(), &message, &signature).is_ok());
        }
    }

    #[test]
    fn signing_is_deterministic() {
        // Not a property of every signature scheme, and the corpus depends on
        // it: a `sign_query` vector asserts bytes, which is only meaningful
        // because two runs agree.
        let key = PrivateKey::from_seed(&known_answers()[0].0).unwrap();
        assert_eq!(key.sign(b"the same message"), key.sign(b"the same message"));
    }

    #[test]
    fn a_signature_over_another_message_is_refused() {
        let key = PrivateKey::from_seed(&known_answers()[0].0).unwrap();
        let signature = key.sign(b"one message");
        assert!(verify(&key.public_key(), b"another message", &signature).is_err());
    }

    #[test]
    fn a_signature_by_another_key_is_refused() {
        let answers = known_answers();
        let signer = PrivateKey::from_seed(&answers[0].0).unwrap();
        let other = PrivateKey::from_seed(&answers[1].0).unwrap();
        let signature = signer.sign(b"a message");
        assert!(verify(&other.public_key(), b"a message", &signature).is_err());
    }

    #[test]
    fn wrong_lengths_are_refused() {
        assert!(PublicKey::from_bytes(&[0u8; 31]).is_err());
        assert!(PublicKey::from_bytes(&[0u8; 33]).is_err());
        let key = PrivateKey::from_seed(&known_answers()[0].0).unwrap();
        assert!(verify(&key.public_key(), b"", &[0u8; 63]).is_err());
        assert!(verify(&key.public_key(), b"", &[0u8; 65]).is_err());
    }

    /// The group order.
    const L: [u8; 32] = [
        0xed, 0xd3, 0xf5, 0x5c, 0x1a, 0x63, 0x12, 0x58, 0xd6, 0x9c, 0xf7, 0xa2, 0xde, 0xf9, 0xde,
        0x14, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x10,
    ];

    #[test]
    fn a_non_canonical_s_is_refused() {
        // Rule 2. `S + L` is a second encoding of the same scalar, so without
        // this every signature has a twin that verifies — and a `signed`
        // string that can be altered in transit and still verify.
        let key = PrivateKey::from_seed(&known_answers()[0].0).unwrap();
        let signature = key.sign(b"");
        assert!(verify(&key.public_key(), b"", &signature).is_ok());

        let mut twin = signature;
        let mut carry = 0u16;
        for i in 0..32 {
            let sum = twin[32 + i] as u16 + L[i] as u16 + carry;
            twin[32 + i] = sum as u8;
            carry = sum >> 8;
        }
        assert_ne!(twin, signature, "S + L must differ from S");
        assert!(verify(&key.public_key(), b"", &twin).is_err());
    }

    // The identity point, and the point of order two. `A = R = identity` with
    // `S = 0` satisfies the verification equation for **every** message.
    const IDENTITY: &str = "0100000000000000000000000000000000000000000000000000000000000000";
    const ORDER_TWO: &str = "ecffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff7f";

    #[test]
    fn a_small_order_key_is_refused_before_it_is_a_key() {
        // Rule 3, enforced in the type: this never reaches `verify`.
        for point in [IDENTITY, ORDER_TWO] {
            assert!(PublicKey::from_bytes(&hex(point)).is_err(), "{point}");
        }
    }

    #[test]
    fn a_non_canonical_field_encoding_is_refused() {
        // Rule 1's other half. `y + p` for the twelve values above `p` that are
        // still points on the curve — both libraries accept these, so this is
        // the rule Q2D applies that neither of its dependencies does.
        let p = [
            0xed, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
            0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
            0xff, 0xff, 0xff, 0x7f,
        ];
        let mut above = p;
        above[0] += 3; // y = p + 3
        assert!(PublicKey::from_bytes(&above).is_err());

        // And in `R`, where it reaches `verify` rather than key construction.
        let key = PrivateKey::from_seed(&known_answers()[0].0).unwrap();
        let signature = key.sign(b"");
        let mut forged = signature;
        forged[..32].copy_from_slice(&above);
        assert!(verify(&key.public_key(), b"", &forged).is_err());

        // The boundary: `y = p - 1` is the largest canonical value and must not
        // be caught by a rule written with `<=` where it needs `<`.
        let mut largest = p;
        largest[0] -= 1;
        assert!(canonical_point(&largest), "p - 1 is canonical");
        assert!(!canonical_point(&p), "p is not");
    }

    #[test]
    fn acceptance_differs_from_the_permissive_rule() {
        // The whole reason this module states its criteria instead of
        // inheriting them. Under the permissive rule the identity forgery is a
        // valid signature over any message, by anyone, with no private key.
        //
        // `PublicKey::from_bytes` refuses the key, so the forgery is built
        // against dalek's own type to show the difference is in the rule and
        // not in this wrapper.
        let raw: [u8; 32] = hex(IDENTITY).try_into().unwrap();
        let weak = PublicKey(ed25519_dalek::VerifyingKey::from_bytes(&raw).unwrap());
        let forgery = [hex(IDENTITY), vec![0u8; 32]].concat();

        for message in [b"".as_slice(), b"any message at all", b"or this one"] {
            assert!(
                verify_permissive(&weak, message, &forgery),
                "the permissive rule was expected to accept the forgery"
            );
            assert!(
                verify(&weak, message, &forgery).is_err(),
                "Q2D's rule must refuse it"
            );
        }
    }
}
