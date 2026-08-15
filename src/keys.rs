//! Key resolution — the interface, and a fixture implementation for tests.
//!
//! P-003 issue 9, §4.6. `resolve(key_id) -> Result<PublicKey, _>` is **the
//! entire surface this PRD owns**. Where a key comes from, how it was
//! established, how it rotates, and whether a delegation chain authorizes it
//! are [P-014](https://github.com/q2d-protocol/q2d/blob/main/docs/prds/P-014-identity-pairing.md)'s.
//!
//! ## Two invariants, and they are the reason this is an interface at all
//!
//! **A key that cannot be resolved is a rejection, never a default.** No
//! fallback key, no "try the last known good", no unauthenticated acceptance.
//! The signature of [`KeyResolver::resolve`] carries that: it returns a key or
//! an error, and there is no third case for a caller to be lenient about.
//!
//! **Its failure is indistinguishable on the wire from a signature failure.**
//! Both are `core-model.md` §5.2.1's `unauthenticated`, because distinguishing
//! them tells a requester whether a key is *known* — which is relationship
//! existence, and is disclosure whether or not the exchange proceeds. That is
//! why this module's error type is [`crate::ed25519::SignatureInvalid`] rather
//! than one of its own: **there is no second value to accidentally map onto a
//! second response.**
//!
//! ## `key_id` is a lookup, never a locator
//!
//! §4.1: the identifier is attacker-controlled and read before anything is
//! authenticated. A resolver that treated it as a path or a URL would fetch
//! what an attacker named, before verifying anything. It indexes a set the
//! implementation already trusts, and nothing else.

use crate::ed25519::{PublicKey, SignatureInvalid};
use std::collections::BTreeMap;

/// Resolve a key identifier to a public key this implementation already trusts.
pub trait KeyResolver {
    /// The key, or a rejection. There is no third answer.
    fn resolve(&self, key_id: &str) -> Result<PublicKey, SignatureInvalid>;
}

/// A resolver over a fixed set — the test fixture, and the shape P-014 replaces.
///
/// **Test material only**, and it says so where it is built: the keys it holds
/// come from `conformance/keys/ed25519-test-only.json`, whose seeds are
/// published in RFC 8032 and known to everyone.
#[derive(Debug, Clone, Default)]
pub struct FixedKeys {
    keys: BTreeMap<String, PublicKey>,
}

impl FixedKeys {
    /// An empty resolver, which resolves nothing.
    pub fn new() -> Self {
        Self::default()
    }

    /// Add a key. Fails if the bytes are not one `crypto-suites.md` §3 admits —
    /// a small-order or non-canonically-encoded key never enters the set, so it
    /// cannot be resolved later and then refused at verification.
    pub fn with(mut self, key_id: &str, public_key: &[u8]) -> Result<Self, SignatureInvalid> {
        self.keys
            .insert(key_id.to_string(), PublicKey::from_bytes(public_key)?);
        Ok(self)
    }
}

impl KeyResolver for FixedKeys {
    fn resolve(&self, key_id: &str) -> Result<PublicKey, SignatureInvalid> {
        // `cloned` rather than a reference so that a caller cannot hold a
        // borrow of the set across a rotation. Copying 32 bytes is not the
        // expensive part of anything here.
        self.keys.get(key_id).cloned().ok_or(SignatureInvalid)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::ed25519::PrivateKey;

    fn a_key() -> (Vec<u8>, PrivateKey) {
        let seed = vec![7u8; 32];
        let key = PrivateKey::from_seed(&seed).unwrap();
        (key.public_key().to_bytes().to_vec(), key)
    }

    #[test]
    fn a_known_key_resolves() {
        let (public, _) = a_key();
        let resolver = FixedKeys::new().with("test-requester-1", &public).unwrap();
        assert_eq!(
            resolver.resolve("test-requester-1").unwrap().to_bytes().to_vec(),
            public
        );
    }

    #[test]
    fn an_unknown_key_is_a_rejection_and_not_a_default() {
        let (public, _) = a_key();
        let resolver = FixedKeys::new().with("test-requester-1", &public).unwrap();
        assert!(resolver.resolve("someone-else").is_err());
        // And an empty resolver resolves nothing rather than everything, which
        // is the direction a "fall back to the only key" convenience fails in.
        assert!(FixedKeys::new().resolve("test-requester-1").is_err());
    }

    #[test]
    fn the_failure_is_the_same_value_a_bad_signature_produces() {
        // §4.6's second invariant, carried by the type. These are not merely
        // equal today — they are the same type with one inhabitant, so there is
        // no second value for a caller to map onto a second wire response.
        let (public, key) = a_key();
        let resolver = FixedKeys::new().with("test-requester-1", &public).unwrap();

        let unresolvable = resolver.resolve("someone-else").unwrap_err();
        let bad_signature =
            crate::ed25519::verify(&key.public_key(), b"a message", &[0u8; 64]).unwrap_err();
        assert_eq!(unresolvable, bad_signature);
        assert_eq!(unresolvable.to_string(), bad_signature.to_string());
    }

    #[test]
    fn a_key_the_suite_would_refuse_never_enters_the_set() {
        // The identity point. Rejected at insertion, so it cannot resolve and
        // then fail verification — one refusal, at the boundary, rather than
        // two chances to get it right.
        let identity = [
            1u8, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
            0, 0, 0, 0,
        ];
        assert!(FixedKeys::new().with("attacker", &identity).is_err());
    }
}
